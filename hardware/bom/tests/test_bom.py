"""Test BOM thiết kế: lược đồ, trạng thái xác minh, linh kiện bắt buộc."""

from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOM_DIR = ROOT / "hardware" / "bom"
HEADER = [
    "ref", "block", "value", "mpn", "manufacturer", "package",
    "qty", "dnp", "verify", "notes",
]
VERIFY = {"candidate", "verified-datasheet", "not-chosen", "dnp"}


def load(name: str) -> list[dict[str, str]]:
    with (BOM_DIR / name).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADER:
            raise AssertionError(f"{name}: header sai: {reader.fieldnames}")
        return list(reader)


class BomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pwr = load("pwr-rev-a.csv")
        self.cmp = load("cmp-rev-b.csv")

    def test_rows_exist(self) -> None:
        self.assertGreaterEqual(len(self.pwr), 20)
        self.assertGreaterEqual(len(self.cmp), 12)

    def test_row_rules(self) -> None:
        for name, rows in (("pwr", self.pwr), ("cmp", self.cmp)):
            for row in rows:
                with self.subTest(bom=name, ref=row["ref"]):
                    for field in ("ref", "block", "value"):
                        self.assertTrue(row[field].strip(), f"thieu {field}")
                    self.assertIn(row["dnp"], {"yes", "no"})
                    self.assertIn(row["verify"], VERIFY)
                    self.assertGreater(int(row["qty"]), 0)
                    if row["verify"] == "not-chosen":
                        self.assertTrue(row["notes"].strip(), "not-chosen phai ghi ly do")
                    elif row["dnp"] == "no":
                        self.assertTrue(row["mpn"].strip(), "dnp=no phai co MPN")
                        self.assertIn(
                            row["verify"], {"candidate", "verified-datasheet"}
                        )
                    else:
                        self.assertIn(row["verify"], {"not-chosen", "dnp"})

    def test_refs_unique_per_board(self) -> None:
        for name, rows in (("pwr", self.pwr), ("cmp", self.cmp)):
            refs = [row["ref"] for row in rows]
            self.assertEqual(len(refs), len(set(refs)), f"{name}: trung ref")

    def test_b2b_matches_between_boards(self) -> None:
        def b2b(rows: list[dict[str, str]]) -> dict[str, str]:
            found = [row for row in rows if row["block"] == "b2b"]
            self.assertEqual(len(found), 1)
            return found[0]

        pwr = b2b(self.pwr)
        cmp = b2b(self.cmp)
        self.assertEqual(pwr["mpn"], cmp["mpn"])
        self.assertEqual(pwr["qty"], "1")
        self.assertEqual(cmp["qty"], "1")

    def test_required_blocks_present(self) -> None:
        pwr_blocks = {row["block"] for row in self.pwr}
        cmp_blocks = {row["block"] for row in self.cmp}
        for block in ("boost", "buck", "charger", "mcu", "b2b", "pack"):
            self.assertIn(block, pwr_blocks, f"pwr thieu block {block}")
        for block in ("soc", "camera", "modem", "usb_mux", "b2b", "sd"):
            self.assertIn(block, cmp_blocks, f"cmp thieu block {block}")

    def test_key_parts_are_the_chosen_ones(self) -> None:
        text = ",".join(row["mpn"] for row in self.pwr + self.cmp)
        for part in (
            "TPS61088", "TPS62840", "Core1106D1408", "TS3USB221",
        ):
            self.assertIn(part, text)

    def test_charger_is_explicitly_unresolved(self) -> None:
        charger = [row for row in self.pwr if row["block"] == "charger"]
        self.assertEqual(len(charger), 1)
        row = charger[0]
        self.assertEqual(row["verify"], "not-chosen")
        text = (row["notes"] + " " + row["value"]).lower()
        self.assertIn("4.2", text)
        self.assertIn("hardware", text)

    def test_package_regressions(self) -> None:
        expected = {
            "TPS62840DLCR": "SON-8 1.5x2mm",
            "M24C32-FMN6TP": "SO-8 150mil",
        }
        seen = {row["mpn"]: row["package"] for row in self.pwr}
        for mpn, package in expected.items():
            self.assertEqual(seen.get(mpn), package, f"goi sai cho {mpn}")

    def test_readme_exists(self) -> None:
        self.assertTrue((BOM_DIR / "README.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
