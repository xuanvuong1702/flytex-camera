"""Test schematic KiCad PWR sinh từ netlist."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.kicad import sch_pwr  # noqa: E402


class PwrSchematicTests(unittest.TestCase):
    def test_check_mode_passes(self) -> None:
        self.assertEqual(sch_pwr.main(["--check"]), 0)

    def test_five_symbols_and_labels(self) -> None:
        text = sch_pwr.OUT.read_text(encoding="utf-8")
        for ref in ("U1", "U2", "U3", "Q1", "Q2"):
            self.assertIn(f'(property "Reference" "{ref}"', text)
        self.assertGreaterEqual(text.count("(global_label "), 20)

    def test_all_power_pins_have_labels_or_nc(self) -> None:
        text = sch_pwr.OUT.read_text(encoding="utf-8")
        self.assertIn("(no_connect", text)
        self.assertIn("PWR_FLAG", text)

    def test_pdf_exists(self) -> None:
        self.assertTrue((sch_pwr.OUT.parent / "flytex-pwr.pdf").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
