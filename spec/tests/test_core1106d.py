"""Kiểm tra dữ liệu chân Core1106D nhập từ tài liệu Luckfox."""

from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIN_CSV = ROOT / "spec" / "core1106d" / "pins.csv"


class CorePinoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with PIN_CSV.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_has_112_pins_in_order(self) -> None:
        pins = [int(row["pin"]) for row in self.rows]
        self.assertEqual(pins, list(range(1, 113)))

    def test_names_are_not_empty(self) -> None:
        for row in self.rows:
            self.assertTrue(row["name"].strip(), f"chan {row['pin']} thieu ten")

    def test_has_mipi_usb_and_uart(self) -> None:
        names = " ".join(row["name"] for row in self.rows)
        self.assertIn("MIPI_CSI", names)
        self.assertIn("USB", names)
        self.assertIn("UART", names)

    def test_has_power_and_ground_pins(self) -> None:
        names = {row["name"] for row in self.rows}
        self.assertTrue(any("GND" in name for name in names))
        self.assertTrue(any("VCC" in name or "3V3" in name or "1V8" in name for name in names))

    def test_source_is_recorded(self) -> None:
        text = (PIN_CSV.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("Core1106D-PinOut.xls", text)
        self.assertIn("112", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
