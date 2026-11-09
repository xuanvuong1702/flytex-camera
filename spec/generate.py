#!/usr/bin/env python3
"""Sinh mã và bảng từ spec/ (nguồn sự thật duy nhất).

    python spec/generate.py           # ghi lại các file sinh
    python spec/generate.py --check   # CI: báo lỗi nếu file sinh lệch spec

Không sửa tay file trong spec/generated, app/flytex/regs_gen.py,
app/flytex/mqtt_gen.py hay firmware/mcu/include/flytex/regs_gen.h.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
GEN = SPEC / "generated"

ACCESS_CODE = {"ro": 0, "rw": 1, "wo": 2}
FLAG_CLEAR_ON_READ = 1 << 0
FLAG_LATCH_READ = 1 << 1
FLAG_COMMIT_WRITE = 1 << 2
FLAG_SIGNED = 1 << 3


class SpecError(Exception):
    pass


def load(name: str) -> dict:
    path = SPEC / name
    with path.open("rb") as fh:
        return tomllib.load(fh)


# --------------------------------------------------------------------------
# Kiểm tra tính hợp lệ của spec
# --------------------------------------------------------------------------

def validate_regs(spec: dict) -> None:
    bus = spec["bus"]
    regs = spec["regs"]
    if bus["proto_major"] > 0xF or bus["proto_minor"] > 0xF:
        raise SpecError("phiên bản giao thức phải vừa 4 bit")
    if not 0 <= bus["i2c_address"] <= 0x7F:
        raise SpecError("địa chỉ I2C 7 bit không hợp lệ")

    seen_addr: dict[int, str] = {}
    seen_name: set[str] = set()
    for reg in regs:
        name = reg["name"]
        if name in seen_name:
            raise SpecError(f"trùng tên thanh ghi: {name}")
        seen_name.add(name)
        if reg["access"] not in ACCESS_CODE:
            raise SpecError(f"{name}: access không hợp lệ")
        size = reg.get("size", 1)
        if size not in (1, 2, 4):
            raise SpecError(f"{name}: size phải là 1, 2 hoặc 4")
        for i in range(size):
            if reg["addr"] + i in seen_addr:
                raise SpecError(
                    f"{name} chồng lên {seen_addr[reg['addr'] + i]} tại 0x{reg['addr'] + i:02X}"
                )
            seen_addr[reg["addr"] + i] = name
        if reg["addr"] + size > bus["reg_count"]:
            raise SpecError(f"{name}: vượt quá reg_count")
        if reg.get("order", "be") != "be":
            raise SpecError(f"{name}: chỉ hỗ trợ big-endian")
        for bit in reg.get("bits", []):
            if not 0 <= bit["bit"] < 8 * size:
                raise SpecError(f"{name}: bit {bit['bit']} ngoài dải")
        if "values" in reg:
            for item in reg["values"]:
                if not 0 <= item["value"] <= 0xFF:
                    raise SpecError(f"{name}: giá trị enum ngoài 1 byte")
        if reg.get("signed") and reg.get("invalid") is not None:
            invalid = reg["invalid"]
            if not 0 <= invalid <= 0xFF:
                raise SpecError(f"{name}: invalid phải là 1 byte")
            if not _has_value(reg, "invalid"):
                pass

    proto = spec["regs"][0]
    expected = (bus["proto_major"] << 4) | bus["proto_minor"]
    if proto["name"] != "PROTO_VER" or proto["addr"] != 0x00:
        raise SpecError("PROTO_VER phải là thanh ghi đầu tiên tại 0x00")
    if proto["reset"] != expected:
        raise SpecError(
            f"PROTO_VER reset 0x{proto['reset']:02X} != (major<<4|minor) 0x{expected:02X}"
        )

    event = _reg(regs, "EVENT")
    mask = _reg(regs, "EVENT_MASK")
    if event["size"] != mask["size"]:
        raise SpecError("EVENT và EVENT_MASK phải cùng kích thước")


def _has_value(reg: dict, key: str) -> bool:
    return any(item.get("name", "").lower() == key for item in reg.get("values", []))


def _reg(regs: list[dict], name: str) -> dict:
    for reg in regs:
        if reg["name"] == name:
            return reg
    raise SpecError(f"thiếu thanh ghi bắt buộc: {name}")


def validate_b2b(spec: dict) -> None:
    conn = spec["connector"]
    pins = spec["pins"]
    if len(pins) != conn["pins_total"]:
        raise SpecError("số phần tử [[pins]] khác pins_total")
    nums = [pin["num"] for pin in pins]
    if nums != list(range(1, conn["pins_total"] + 1)):
        raise SpecError("số chân phải liên tục từ 1")
    known = set(spec.get("requirements", {}))
    power_nets = {
        pin["net"]
        for pin in pins
        if pin["net"].startswith("+") or pin["net"] == "GND"
    }
    missing = sorted(power_nets - known)
    if missing:
        raise SpecError(f"net nguồn thiếu [requirements]: {', '.join(missing)}")
    for pin in pins:
        if pin.get("max_a", 1.0) > spec["limits"]["max_current_per_pin_a"]:
            raise SpecError(f"chân {pin['num']}: dòng vượt giới hạn mỗi chân")
        if pin["dir"] not in ("PWR->CMP", "CMP->PWR", "bidir", "-"):
            raise SpecError(f"chân {pin['num']}: dir không hợp lệ")


def validate_mqtt(spec: dict) -> None:
    types = [event["type"] for event in spec["events"]]
    if len(types) != len(set(types)):
        raise SpecError("trùng loại sự kiện")
    cmds = [cmd["cmd"] for cmd in spec["commands"]]
    if len(cmds) != len(set(cmds)):
        raise SpecError("trùng tên lệnh")
    for event in spec["events"]:
        names = [field["name"] for field in event["fields"]]
        if len(names) != len(set(names)):
            raise SpecError(f"{event['type']}: trùng tên trường")
        if event.get("retain") and event["qos"] == 0:
            raise SpecError(f"{event['type']}: retained cần QoS >= 1")


# --------------------------------------------------------------------------
# Sinh header C
# --------------------------------------------------------------------------

def gen_regs_h(spec: dict) -> str:
    bus = spec["bus"]
    regs = spec["regs"]
    out: list[str] = []
    w = out.append
    w("/* AUTOGENERATED from spec/registers.toml. Không sửa tay. */")
    w("#ifndef FLYTEX_REGS_GEN_H")
    w("#define FLYTEX_REGS_GEN_H")
    w("")
    w("#include <stdint.h>")
    w("")
    w(f"#define FLY_I2C_ADDR 0x{bus['i2c_address']:02X}u")
    w(f"#define FLY_PROTO_MAJOR {bus['proto_major']}u")
    w(f"#define FLY_PROTO_MINOR {bus['proto_minor']}u")
    w(f"#define FLY_PROTO_VER 0x{(bus['proto_major'] << 4) | bus['proto_minor']:02X}u")
    w(f"#define FLY_REG_COUNT 0x{bus['reg_count']:02X}u")
    w(f"#define FLY_I2C_SPEED_HZ {bus['speed_hz_default']}u")
    w("")
    w("/* Địa chỉ thanh ghi. */")
    for reg in regs:
        w(f"#define FLY_REG_{reg['name']} 0x{reg['addr']:02X}u")
    w("")
    w("/* Bitfield. */")
    for reg in regs:
        bits = reg.get("bits", [])
        if not bits:
            continue
        w(f"/* {reg['name']} */")
        for bit in bits:
            w(f"#define FLY_{reg['name']}_{bit['name']} (1u << {bit['bit']})")
    w("")
    w("/* Mã lệnh, lỗi, chế độ, kênh đánh thức. */")
    enum_names = {
        "CMD": "fly_cmd_t",
        "FAULT_CODE": "fly_fault_t",
        "MODE": "fly_mode_t",
        "WAKE_CHAN": "fly_wake_chan_t",
    }
    prefix = {"CMD": "FLY_CMD_", "FAULT_CODE": "FLY_FAULT_", "MODE": "FLY_MODE_",
              "WAKE_CHAN": "FLY_WAKE_CHAN_"}
    for reg in regs:
        if reg["name"] not in enum_names:
            continue
        w(f"typedef enum {{")
        for item in reg["values"]:
            w(f"    {prefix[reg['name']]}{item['name']} = {item['value']},")
        w(f"}} {enum_names[reg['name']]};")
        w("")
    w("/* Bảng mô tả thanh ghi để hiện thực kiểm tra truy cập. */")
    w("#define FLY_ACCESS_RO 0u")
    w("#define FLY_ACCESS_RW 1u")
    w("#define FLY_ACCESS_WO 2u")
    w("#define FLY_RF_CLEAR_ON_READ (1u << 0)")
    w("#define FLY_RF_LATCH_READ (1u << 1)")
    w("#define FLY_RF_COMMIT_WRITE (1u << 2)")
    w("#define FLY_RF_SIGNED (1u << 3)")
    w("")
    w("typedef struct {")
    w("    uint8_t addr;")
    w("    uint8_t size;")
    w("    uint8_t access;")
    w("    uint8_t flags;")
    w("    uint8_t reset;")
    w("    const char *name;")
    w("} fly_reg_desc_t;")
    w("")
    w(f"#define FLY_REG_DESC_COUNT {len(regs)}u")
    w("extern const fly_reg_desc_t fly_reg_descs[FLY_REG_DESC_COUNT];")
    w("")
    w("#endif /* FLYTEX_REGS_GEN_H */")
    return "\n".join(out) + "\n"


def gen_regs_c(spec: dict) -> str:
    out = [
        "/* AUTOGENERATED from spec/registers.toml. Không sửa tay. */",
        '#include "flytex/regs_gen.h"',
        "",
        "const fly_reg_desc_t fly_reg_descs[FLY_REG_DESC_COUNT] = {",
    ]
    for reg in spec["regs"]:
        flags = []
        if reg.get("clear_on_read"):
            flags.append("FLY_RF_CLEAR_ON_READ")
        if reg.get("latch_read"):
            flags.append("FLY_RF_LATCH_READ")
        if reg.get("commit_write"):
            flags.append("FLY_RF_COMMIT_WRITE")
        if reg.get("signed"):
            flags.append("FLY_RF_SIGNED")
        flag_text = " | ".join(flags) if flags else "0"
        out.append(
            f'    {{0x{reg["addr"]:02X}, {reg.get("size", 1)}, '
            f'FLY_ACCESS_{reg["access"].upper()}, {flag_text}, '
            f'0x{reg["reset"]:02X}, "{reg["name"]}"}},'
        )
    out.append("};")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Sinh module Python
# --------------------------------------------------------------------------

def py_type(reg: dict) -> str:
    if reg.get("signed"):
        return "i8"
    return {1: "u8", 2: "u16", 4: "u32"}[reg.get("size", 1)]


def gen_regs_py(spec: dict) -> str:
    bus = spec["bus"]
    regs = spec["regs"]
    out: list[str] = []
    w = out.append
    w('"""AUTOGENERATED from spec/registers.toml. Không sửa tay."""')
    w("")
    w("from __future__ import annotations")
    w("")
    w("from dataclasses import dataclass")
    w("")
    w(f"I2C_ADDR = 0x{bus['i2c_address']:02X}")
    w(f"PROTO_MAJOR = {bus['proto_major']}")
    w(f"PROTO_MINOR = {bus['proto_minor']}")
    w(f"PROTO_VER = 0x{(bus['proto_major'] << 4) | bus['proto_minor']:02X}")
    w(f"REG_COUNT = 0x{bus['reg_count']:02X}")
    w("")
    w("ACCESS_RO = 'ro'")
    w("ACCESS_RW = 'rw'")
    w("ACCESS_WO = 'wo'")
    w("")
    w("@dataclass(frozen=True)")
    w("class Reg:")
    w("    name: str")
    w("    addr: int")
    w("    access: str")
    w("    size: int")
    w("    reset: int")
    w("    clear_on_read: bool = False")
    w("    latch_read: bool = False")
    w("    commit_write: bool = False")
    w("    signed: bool = False")
    w("    invalid: int | None = None")
    w("")
    w("REGISTERS: tuple[Reg, ...] = (")
    for reg in regs:
        args = [
            f'"{reg["name"]}"',
            f"0x{reg['addr']:02X}",
            f'"{reg["access"]}"',
            str(reg.get("size", 1)),
            f"0x{reg['reset']:02X}",
        ]
        kwargs = []
        if reg.get("clear_on_read"):
            kwargs.append("clear_on_read=True")
        if reg.get("latch_read"):
            kwargs.append("latch_read=True")
        if reg.get("commit_write"):
            kwargs.append("commit_write=True")
        if reg.get("signed"):
            kwargs.append("signed=True")
        if reg.get("invalid") is not None:
            kwargs.append(f"invalid=0x{reg['invalid']:02X}")
        text = "    Reg(" + ", ".join(args + kwargs) + "),"
        w(text)
    w(")")
    w("")
    w("REG_BY_NAME = {reg.name: reg for reg in REGISTERS}")
    w("REG_BY_ADDR = {reg.addr: reg for reg in REGISTERS}")
    w("")
    for const in ("CMD", "FAULT_CODE", "MODE", "WAKE_CHAN"):
        reg = _reg(regs, const)
        w(f"{const} = {{")
        for item in reg["values"]:
            w(f'    "{item["name"]}": {item["value"]},')
        w("}")
        w(f"{const}_NAME = {{value: name for name, value in {const}.items()}}")
        w("")
    for const in ("STATUS", "CHG", "EVENT", "EVENT_MASK", "SYS_FLAGS"):
        reg = _reg(regs, const)
        w(f"{const}_BITS = {{")
        for bit in reg.get("bits", []):
            w(f'    "{bit["name"]}": 1 << {bit["bit"]},')
        w("}")
        w("")
    w("")
    w("def unpack(be: bytes) -> int:")
    w('    """Giải mã big-endian không dấu."""')
    w("    value = 0")
    w("    for byte in be:")
    w("        value = (value << 8) | byte")
    w("    return value")
    w("")
    w("")
    w("def pack(value: int, size: int) -> bytes:")
    w('    """Đóng gói big-endian."""')
    w("    if not 0 <= value < (1 << (8 * size)):")
    w("        raise ValueError(f'giá trị {value} không vừa {size} byte')")
    w("    return value.to_bytes(size, 'big')")
    w("")
    w("")
    w("def decode_int8(raw: int) -> int | None:")
    w('    """-1..127, 0x80 là không hợp lệ (None)."""')
    w("    if raw == 0x80:")
    w("        return None")
    w("    return raw - 256 if raw >= 0x80 else raw")
    w("")
    w("")
    w("def decode_event(mask: int) -> set[str]:")
    w("    return {name for name, bit in EVENT_BITS.items() if mask & bit}")
    w("")
    w("")
    w("def encode_event(names: set[str]) -> int:")
    w("    mask = 0")
    w("    for name in names:")
    w("        mask |= EVENT_BITS[name]")
    w("    return mask")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Sinh bảng markdown
# --------------------------------------------------------------------------

def gen_regmap_md(spec: dict) -> str:
    bus = spec["bus"]
    regs = spec["regs"]
    out: list[str] = []
    w = out.append
    w("# Regmap MCU ↔ SoC (sinh tự động)")
    w("")
    w(f"- Nguồn: `spec/registers.toml`")
    w(f"- Địa chỉ I2C 7 bit: `0x{bus['i2c_address']:02X}`")
    w(f"- Phiên bản giao thức: **{bus['proto_major']}.{bus['proto_minor']}**")
    w(f"- Số byte vùng thanh ghi: `0x{bus['reg_count']:02X}`")
    w("")
    w("## 1. Thanh ghi")
    w("")
    w("| Địa chỉ | Tên | R/W | Byte | Reset | Mô tả |")
    w("|---|---|---|---|---|---|")
    for reg in regs:
        access = {"ro": "R", "rw": "R/W", "wo": "W"}[reg["access"]]
        addr = f"0x{reg['addr']:02X}"
        if reg.get("size", 1) > 1:
            addr += f"–0x{reg['addr'] + reg['size'] - 1:02X}"
        w(f"| {addr} | {reg['name']} | {access} | {reg.get('size', 1)} | "
          f"0x{reg['reset']:02X} | {reg['desc']} |")
    w("")
    w("## 2. Bitfield")
    w("")
    for reg in regs:
        bits = reg.get("bits", [])
        if not bits:
            continue
        w(f"### {reg['name']}")
        w("")
        w("| Bit | Tên | Mô tả |")
        w("|---|---|---|")
        for bit in bits:
            w(f"| {bit['bit']} | {bit['name']} | {bit.get('desc', '')} |")
        w("")
    w("## 3. Mã lệnh, lỗi, chế độ")
    w("")
    for name in ("CMD", "FAULT_CODE", "MODE", "WAKE_CHAN"):
        reg = _reg(regs, name)
        w(f"### {name}")
        w("")
        w("| Giá trị | Tên | Mô tả |")
        w("|---|---|---|")
        for item in reg["values"]:
            w(f"| {item['value']} | {item['name']} | {item.get('desc', '')} |")
        w("")
    w("## 4. Quy tắc truy cập")
    w("")
    w("1. Thanh ghi nhiều byte là big-endian: byte cao ở địa chỉ thấp.")
    w("2. Đọc byte cao chốt (latch) toàn bộ nhóm; các byte sau trả giá trị đã chốt.")
    w("3. Ghi nhóm nhiều byte từ địa chỉ thấp tới cao; byte cuối cùng commit giá trị mới.")
    w("4. `EVENT` xóa khi đọc. Đọc trả các bit đã đặt rồi xóa chúng.")
    w("5. Ghi vào thanh ghi chỉ đọc, ghi ngoài dải, hoặc mã `CMD` lạ: NACK / đặt `BAD_CMD`.")
    w("6. Thanh ghi không định nghĩa trong bảng trên: NACK, không trả 0 im lặng.")
    return "\n".join(out) + "\n"


def gen_b2b_md(spec: dict) -> str:
    conn = spec["connector"]
    limits = spec["limits"]
    reqs = spec.get("requirements", {})
    out: list[str] = []
    w = out.append
    w("# J_B2B — pinout PWR ↔ CMP (sinh tự động)")
    w("")
    w(f"- Nguồn: `spec/b2b.toml`")
    w(f"- Connector: **{conn['type']}**, {conn['pins_total']} chân")
    w(f"- Mức logic: {conn['logic_level_v']} V")
    w("")
    w("| Chân | Tín hiệu | Hướng | Dòng tối đa (A) | Ghi chú |")
    w("|---|---|---|---|---|")
    for pin in spec["pins"]:
        w(f"| {pin['num']} | {pin['name']} | {pin['dir']} | "
          f"{pin.get('max_a', '')} | {pin.get('desc', pin.get('pullup', ''))} |")
    w("")
    w("## Ngân sách dòng theo net")
    w("")
    w("| Net | Số chân | Tổng dòng chân (A) | Yêu cầu thiết kế (A) | Dư | Đạt |")
    w("|---|---|---|---|---|---|")
    net_pins: dict[str, list[dict]] = {}
    for pin in spec["pins"]:
        net_pins.setdefault(pin["net"], []).append(pin)
    ok_all = True
    for net, pins in net_pins.items():
        if net not in reqs:
            continue
        total = sum(pin.get("max_a", 1.0) for pin in pins)
        need = reqs[net]["require_a"]
        margin = float("inf") if need == 0 else total / need
        ok = margin >= limits["min_current_margin"]
        ok_all = ok_all and ok
        w(f"| {net} | {len(pins)} | {total:.2f} | {need:.2f} | {margin:.2f}× | "
          f"{'có' if ok else '**không**'} |")
    w("")
    if not ok_all:
        w("> **Cảnh báo:** có net không đạt hệ số dư tối thiểu "
          f"{limits['min_current_margin']}×. Không được đặt board trước khi sửa.")
    else:
        w(f"Tất cả net đạt hệ số dư tối thiểu {limits['min_current_margin']}×.")
    w("")
    w("## Ghi chú thiết kế")
    w("")
    w("- Đây là hợp đồng giữa hai board: đổi file này phải đổi cả PWR và CMP, và tăng phiên bản.")
    w("- Các chân dự phòng không được dùng cho chức năng bắt buộc.")
    w("- Cáp B2B phải ngắn; nếu dài quá 60 mm, cần kiểm tra lại I2C và dòng.")
    return "\n".join(out) + "\n"


def gen_pinout_csv(spec: dict) -> str:
    lines = ["pin,signal,net,direction,max_a"]
    for pin in spec["pins"]:
        lines.append(
            f"{pin['num']},{pin['name']},{pin['net']},{pin['dir']},{pin.get('max_a', '')}"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Sinh MQTT
# --------------------------------------------------------------------------

def gen_mqtt_json(spec: dict) -> str:
    doc = {
        "schema": spec["schema"],
        "version": spec["version"],
        "topics": spec["topic"],
        "envelope": spec["envelope"]["fields"],
        "events": {
            event["type"]: {
                "qos": event["qos"],
                "retain": event.get("retain", False),
                "description": event.get("desc", ""),
                "fields": event["fields"],
            }
            for event in spec["events"]
        },
        "commands": {
            cmd["cmd"]: {
                "description": cmd.get("desc", ""),
                "args": cmd.get("args", []),
                "result": cmd.get("result", []),
            }
            for cmd in spec["commands"]
        },
        "ack": spec["ack"]["fields"],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def gen_mqtt_py(spec: dict) -> str:
    out = [
        '"""AUTOGENERATED from spec/mqtt.toml. Không sửa tay."""',
        "",
        "from __future__ import annotations",
        "",
        f"VERSION = {spec['version']}",
        f"QOS_DEFAULT = {spec['qos_default']}",
        "",
    ]
    names = {"evt": "TOPIC_EVT", "status": "TOPIC_STATUS", "cmd": "TOPIC_CMD", "ack": "TOPIC_ACK"}
    for key, const in names.items():
        out.append(f'{const} = "{spec["topic"][key]}"')
    out += ["", "ENVELOPE_FIELDS = ("]
    for field in spec["envelope"]["fields"]:
        out.append(f'    ("{field["name"]}", {field["required"]!r}),')
    out += [")", "", "EVENT_TYPES = ("]
    for event in spec["events"]:
        out.append(f'    "{event["type"]}",')
    out += [")", "", "EVENT_FIELDS = {"]
    for event in spec["events"]:
        fields = ", ".join(f'"{field["name"]}"' for field in event["fields"])
        out.append(f'    "{event["type"]}": ({fields}),')
    out += ["}", "", "EVENT_REQUIRED = {"]
    for event in spec["events"]:
        fields = ", ".join(f'"{field["name"]}"' for field in event["fields"] if field.get("required"))
        out.append(f'    "{event["type"]}": ({fields}),')
    out += ["}", "", "EVENT_RETAIN = {"]
    for event in spec["events"]:
        out.append(f'    "{event["type"]}": {bool(event.get("retain", False))!r},')
    out += ["}", "", "COMMANDS = {"]
    for cmd in spec["commands"]:
        args = ", ".join(
            f'"{arg["name"]}": {{"required": {arg.get("required", False)!r}, "type": "{arg["type"]}"}}'
            for arg in cmd.get("args", [])
        )
        out.append(f'    "{cmd["cmd"]}": {{{args}}},')
    out += ["}", "", "ACK_ERRORS = ("]
    out += ['    "BAD_ARGS",', '    "BAD_ID",', '    "BUSY",', '    "NOT_IMPLEMENTED",',
            '    "INTERNAL",', ")", ""]
    out += [
        "",
        "def event_topic(dev: str) -> str:",
        "    return TOPIC_EVT.format(dev=dev)",
        "",
        "",
        "def status_topic(dev: str) -> str:",
        "    return TOPIC_STATUS.format(dev=dev)",
        "",
        "",
        "def cmd_topic(dev: str) -> str:",
        "    return TOPIC_CMD.format(dev=dev)",
        "",
        "",
        "def ack_topic(dev: str) -> str:",
        "    return TOPIC_ACK.format(dev=dev)",
    ]
    return "\n".join(out) + "\n"


def gen_mqtt_md(spec: dict) -> str:
    out: list[str] = []
    w = out.append
    w("# Hợp đồng MQTT (sinh tự động)")
    w("")
    w(f"- Nguồn: `spec/mqtt.toml`, phiên bản lược đồ {spec['version']}")
    w("")
    w("## 1. Chủ đề")
    w("")
    w("| Tên | Mẫu |")
    w("|---|---|")
    for key, value in spec["topic"].items():
        w(f"| {key} | `{value}` |")
    w("")
    w("## 2. Phong bì")
    w("")
    w("| Trường | Kiểu | Bắt buộc | Mô tả |")
    w("|---|---|---|---|")
    for field in spec["envelope"]["fields"]:
        w(f"| {field['name']} | {field['type']} | {'có' if field['required'] else 'không'} | "
          f"{field.get('desc', '')} |")
    w("")
    w("## 3. Sự kiện")
    w("")
    for event in spec["events"]:
        w(f"### `{event['type']}`")
        w("")
        w(f"- QoS {event['qos']}, retained: {'có' if event.get('retain') else 'không'}")
        w(f"- {event.get('desc', '')}")
        w("")
        w("| Trường | Kiểu | Bắt buộc | Mô tả |")
        w("|---|---|---|---|")
        for field in event["fields"]:
            kind = field["type"]
            if isinstance(kind, list):
                kind = " hoặc ".join(kind)
            w(f"| {field['name']} | {kind} | {'có' if field.get('required') else 'không'} | "
              f"{field.get('desc', '')} |")
        w("")
    w("## 4. Lệnh")
    w("")
    for cmd in spec["commands"]:
        w(f"### `{cmd['cmd']}`")
        w("")
        w(cmd.get("desc", ""))
        w("")
        if cmd.get("args"):
            w("| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |")
            w("|---|---|---|---|---|")
            for arg in cmd["args"]:
                kind = arg["type"]
                if isinstance(kind, list):
                    kind = " hoặc ".join(kind)
                w(f"| {arg['name']} | {kind} | {'có' if arg.get('required') else 'không'} | "
                  f"{arg.get('default', '')} | {arg.get('desc', '')} |")
        else:
            w("Không có tham số.")
        w("")
    w("## 5. Xác nhận")
    w("")
    w("| Trường | Kiểu | Bắt buộc | Mô tả |")
    w("|---|---|---|---|")
    for field in spec["ack"]["fields"]:
        kind = field["type"]
        if isinstance(kind, list):
            kind = " hoặc ".join(kind)
        w(f"| {field['name']} | {kind} | {'có' if field.get('required') else 'không'} | "
          f"{field.get('desc', '')} |")
    w("")
    w("Mã lỗi trong `ack.error`: `BAD_ARGS`, `BAD_ID`, `BUSY`, `NOT_IMPLEMENTED`, `INTERNAL`.")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Điều phối
# --------------------------------------------------------------------------

def build_all() -> dict[Path, str]:
    regs = load("registers.toml")
    b2b = load("b2b.toml")
    mqtt = load("mqtt.toml")
    validate_regs(regs)
    validate_b2b(b2b)
    validate_mqtt(mqtt)
    return {
        ROOT / "firmware/mcu/include/flytex/regs_gen.h": gen_regs_h(regs),
        ROOT / "firmware/mcu/src/regs_gen.c": gen_regs_c(regs),
        ROOT / "app/flytex/regs_gen.py": gen_regs_py(regs),
        GEN / "regmap.md": gen_regmap_md(regs),
        GEN / "b2b.md": gen_b2b_md(b2b),
        GEN / "pinout_pwr_cmp.csv": gen_pinout_csv(b2b),
        GEN / "mqtt.md": gen_mqtt_md(mqtt),
        GEN / "mqtt.schema.json": gen_mqtt_json(mqtt),
        ROOT / "app/flytex/mqtt_gen.py": gen_mqtt_py(mqtt),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi")
    args = parser.parse_args(argv)
    try:
        files = build_all()
    except (SpecError, KeyError) as exc:
        print(f"LỖI SPEC: {exc}", file=sys.stderr)
        return 2

    stale: list[Path] = []
    for path, content in files.items():
        rel = path.relative_to(ROOT)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != content:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"ghi {rel}")
    if args.check:
        if stale:
            print("File sinh lệch spec, chạy: python spec/generate.py", file=sys.stderr)
            for rel in stale:
                print(f"  - {rel}", file=sys.stderr)
            return 1
        print(f"OK: {len(files)} file sinh khớp spec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
