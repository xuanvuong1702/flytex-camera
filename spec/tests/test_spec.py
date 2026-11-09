"""Test cho spec/ và bộ sinh mã.

Chạy: python spec/tests/test_spec.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

_spec = importlib.util.spec_from_file_location("flytex_generate", ROOT / "spec" / "generate.py")
generate = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(generate)


def load(name: str) -> dict:
    with (ROOT / "spec" / name).open("rb") as fh:
        return tomllib.load(fh)


def load_generated(name: str, path: Path):
    """Nạp file .py sinh mà không cần app/ là package đã cài."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses cần module có trong sys.modules
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SpecValidity(unittest.TestCase):
    def test_valid_specs_pass(self) -> None:
        generate.validate_regs(load("registers.toml"))
        generate.validate_b2b(load("b2b.toml"))
        generate.validate_mqtt(load("mqtt.toml"))

    def test_overlapping_registers_rejected(self) -> None:
        spec = load("registers.toml")
        spec["regs"][1]["addr"] = 0x00
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_duplicate_register_name_rejected(self) -> None:
        spec = load("registers.toml")
        spec["regs"][2]["name"] = spec["regs"][1]["name"]
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_bad_access_rejected(self) -> None:
        spec = load("registers.toml")
        spec["regs"][1]["access"] = "write-only"
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_proto_version_mismatch_rejected(self) -> None:
        spec = load("registers.toml")
        spec["bus"]["proto_minor"] = 0
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_little_endian_rejected(self) -> None:
        spec = load("registers.toml")
        for reg in spec["regs"]:
            if reg["name"] == "VBAT_MV":
                reg["order"] = "le"
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_bit_out_of_range_rejected(self) -> None:
        spec = load("registers.toml")
        for reg in spec["regs"]:
            if reg["name"] == "STATUS":
                reg["bits"][0]["bit"] = 8
        with self.assertRaises(generate.SpecError):
            generate.validate_regs(spec)

    def test_b2b_pin_count_mismatch_rejected(self) -> None:
        spec = load("b2b.toml")
        spec["pins"] = spec["pins"][:-1]
        with self.assertRaises(generate.SpecError):
            generate.validate_b2b(spec)

    def test_b2b_missing_power_requirement_rejected(self) -> None:
        spec = load("b2b.toml")
        del spec["requirements"]["+5V_MODEM"]
        with self.assertRaises(generate.SpecError):
            generate.validate_b2b(spec)

    def test_b2b_pin_gap_rejected(self) -> None:
        spec = load("b2b.toml")
        spec["pins"][3]["num"] = 9
        with self.assertRaises(generate.SpecError):
            generate.validate_b2b(spec)

    def test_mqtt_duplicate_event_rejected(self) -> None:
        spec = load("mqtt.toml")
        spec["events"][1]["type"] = spec["events"][0]["type"]
        with self.assertRaises(generate.SpecError):
            generate.validate_mqtt(spec)

    def test_mqtt_retained_qos0_rejected(self) -> None:
        spec = load("mqtt.toml")
        for event in spec["events"]:
            if event.get("retain"):
                event["qos"] = 0
        with self.assertRaises(generate.SpecError):
            generate.validate_mqtt(spec)


class GeneratedOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.files = generate.build_all()

    def test_all_expected_outputs_present(self) -> None:
        names = {str(path.relative_to(ROOT)).replace("\\", "/") for path in self.files}
        expected = {
            "firmware/mcu/include/flytex/regs_gen.h",
            "firmware/mcu/src/regs_gen.c",
            "app/flytex/regs_gen.py",
            "app/flytex/mqtt_gen.py",
            "spec/generated/regmap.md",
            "spec/generated/b2b.md",
            "spec/generated/mqtt.md",
            "spec/generated/mqtt.schema.json",
            "spec/generated/pinout_pwr_cmp.csv",
        }
        self.assertEqual(names, expected)

    def test_checked_in_files_match_spec(self) -> None:
        for path, content in self.files.items():
            with self.subTest(path=str(path)):
                self.assertTrue(path.exists(), f"thiếu {path}")
                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    content,
                    f"{path} lệch spec; chạy python spec/generate.py",
                )

    def test_c_header_has_protocol_constants(self) -> None:
        header = self.files[ROOT / "firmware/mcu/include/flytex/regs_gen.h"]
        self.assertIn("#define FLY_PROTO_VER 0x11u", header)
        self.assertIn("#define FLY_I2C_ADDR 0x30u", header)
        self.assertIn("#define FLY_REG_EVENT 0x04u", header)
        self.assertIn("fly_reg_descs", header)

    def test_python_module_imports(self) -> None:
        module = load_generated("regs_gen_check", ROOT / "app" / "flytex" / "regs_gen.py")
        self.assertEqual(module.PROTO_VER, 0x11)
        self.assertEqual(module.I2C_ADDR, 0x30)
        self.assertEqual(module.REG_BY_NAME["EVENT"].addr, 0x04)
        self.assertEqual(module.decode_int8(0x80), None)
        self.assertEqual(module.decode_int8(0xFF), -1)
        self.assertEqual(module.decode_event(module.EVENT_BITS["PIR"]), {"PIR"})
        self.assertEqual(module.pack(0x1234, 2), b"\x12\x34")
        self.assertEqual(module.unpack(b"\x12\x34"), 0x1234)

    def test_python_module_rejects_oversize_pack(self) -> None:
        module = load_generated("regs_gen_check2", ROOT / "app" / "flytex" / "regs_gen.py")
        with self.assertRaises(ValueError):
            module.pack(0x10000, 2)

    def test_b2b_margin_all_pass(self) -> None:
        text = self.files[ROOT / "spec" / "generated" / "b2b.md"]
        self.assertIn("Tất cả net đạt hệ số dư", text)
        self.assertNotIn("**không**", text)
        self.assertIn("| +5V_MODEM | 3 |", text)

    def test_b2b_has_ring_indicator(self) -> None:
        text = self.files[ROOT / "spec" / "generated" / "b2b.md"]
        self.assertIn("MODEM_RI", text)
        self.assertIn("| 21 | MODEM_RI |", text)

    def test_mqtt_schema_parses(self) -> None:
        doc = json.loads(self.files[ROOT / "spec" / "generated" / "mqtt.schema.json"])
        self.assertEqual(doc["version"], 1)
        self.assertIn("motion", doc["events"])
        self.assertIn("live.start", doc["commands"])
        self.assertEqual(doc["events"]["status"]["retain"], True)
        for event in doc["events"].values():
            for field in event["fields"]:
                self.assertIn("name", field)

    def test_command_wire_is_flat(self) -> None:
        doc = json.loads(self.files[ROOT / "spec" / "generated" / "mqtt.schema.json"])
        self.assertEqual(doc["command_wire"]["shape"], "flat")
        self.assertIn('"type":"mode.set"', doc["command_wire"]["example"])
        module = load_generated("mqtt_gen_check", ROOT / "app" / "flytex" / "mqtt_gen.py")
        self.assertEqual(module.COMMAND_WIRE, "flat")

    def test_every_command_has_ack_contract(self) -> None:
        doc = json.loads(self.files[ROOT / "spec" / "generated" / "mqtt.schema.json"])
        names = [field["name"] for field in doc["ack"]]
        self.assertEqual(names, ["ok", "result", "error"])

    def test_regmap_md_covers_all_registers(self) -> None:
        text = self.files[ROOT / "spec" / "generated" / "regmap.md"]
        for reg in load("registers.toml")["regs"]:
            self.assertIn(reg["name"], text)

    def test_check_mode_is_clean(self) -> None:
        self.assertEqual(generate.main(["--check"]), 0)

    def test_check_mode_detects_drift(self) -> None:
        target = ROOT / "spec" / "generated" / "regmap.md"
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original + "\nlech\n", encoding="utf-8")
            self.assertEqual(generate.main(["--check"]), 1)
        finally:
            target.write_text(original, encoding="utf-8")

    def test_generation_is_deterministic(self) -> None:
        first = generate.build_all()
        second = generate.build_all()
        for key in first:
            self.assertEqual(first[key], second[key])


class SourceTruth(unittest.TestCase):
    def test_doc_register_map_points_to_spec(self) -> None:
        doc = (ROOT / "docs" / "03-giao-dien.md").read_text(encoding="utf-8")
        self.assertIn("15-giao-thuc-va-cloud.md", doc)

    def test_spec_has_version_note(self) -> None:
        text = (ROOT / "spec" / "registers.toml").read_text(encoding="utf-8")
        self.assertIn("BIG-ENDIAN", text.upper())

    def test_no_handwritten_copy_of_register_table(self) -> None:
        # docs/03 giữ bảng cũ làm lịch sử nhưng phải trỏ sang spec;
        # nếu ai đó chép lại bảng mới vào docs thì test này nhắc.
        doc = (ROOT / "docs" / "15-giao-thuc-va-cloud.md").read_text(encoding="utf-8")
        self.assertNotIn("| 0x11 | SYS_FLAGS |", doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
