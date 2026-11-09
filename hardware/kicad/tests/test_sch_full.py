"""Test schematic KiCad đầy đủ PWR/CMP."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.kicad import sch_full  # noqa: E402


class FullSchematicTests(unittest.TestCase):
    def test_check_mode_passes(self) -> None:
        self.assertEqual(sch_full.main(["--check"]), 0)

    def test_pwr_sheet_has_all_kinds(self) -> None:
        text = (sch_full.OUT_DIR / "flytex-pwr-full.kicad_sch").read_text(encoding="utf-8")
        for ref in ("U1", "U2", "U3", "Q1", "Q2", "R1", "C1", "L1", "J1"):
            self.assertIn(f'(property "Reference" "{ref}"', text)
        self.assertGreaterEqual(text.count("(global_label "), 60)

    def test_cmp_sheet_has_all_kinds(self) -> None:
        text = (sch_full.OUT_DIR / "flytex-cmp-full.kicad_sch").read_text(encoding="utf-8")
        for ref in ("U1", "U2", "J1", "J2", "J3", "J4", "TP1"):
            self.assertIn(f'(property "Reference" "{ref}"', text)
        self.assertGreaterEqual(text.count("(global_label "), 30)

    def test_pdfs_exist(self) -> None:
        for name in ("flytex-pwr-full.pdf", "flytex-cmp-full.pdf"):
            self.assertTrue((sch_full.OUT_DIR / name).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
