"""Test thư viện ký hiệu KiCad sinh từ bảng chân datasheet."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.kicad import symbols  # noqa: E402


class SymbolLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = symbols.OUT.read_text(encoding="utf-8")

    def test_four_power_ics(self) -> None:
        for name in ("BQ25070", "TPS61088", "TPS62840", "TPS22918"):
            self.assertIn(f'(symbol "{name}"', self.text)

    def test_pin_counts_match_datasheet(self) -> None:
        self.assertEqual(
            symbols.counts(self.text),
            {"BQ25070": 11, "TPS61088": 21, "TPS62840": 9, "TPS22918": 6},
        )

    def test_bq25070_bat_and_out_present(self) -> None:
        self.assertIn('(name "BAT"', self.text)
        self.assertIn('(name "OUT"', self.text)
        self.assertIn('(number "11"', self.text)  # PAD

    def test_sw_pins_present(self) -> None:
        # 4 SW của TPS61088 + 1 SW của TPS62840.
        self.assertEqual(self.text.count('(name "SW"'), 5)

    def test_check_mode_passes(self) -> None:
        self.assertEqual(symbols.main(["--check"]), 0)

    def test_pinout_markdown_exists(self) -> None:
        text = (symbols.OUT.parent / "pinout-power.md").read_text(encoding="utf-8")
        self.assertIn("BQ25070", text)
        self.assertIn("| 11 | PAD |", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
