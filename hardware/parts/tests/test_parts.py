"""Test sổ linh kiện: cấu trúc, phủ BOM, phát hiện blocker đúng."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.parts import check


class RegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parts, cls.external = check.load_parts()
        cls.bom = check.load_bom()
        cls.issues = (
            check.structural_issues(cls.parts, cls.external, cls.bom)
            + check.design_issues(cls.parts, cls.external, cls.bom)
        )

    def test_register_is_loaded(self) -> None:
        self.assertGreaterEqual(len(self.parts), 12)
        self.assertEqual(len(self.external), 4)
        for pid, part in self.parts.items():
            self.assertTrue(part.get("mpn"), pid)
            self.assertIn(part.get("verified"), {"yes", "partial", "no"})
        for eid, item in self.external.items():
            self.assertIn(item.get("verified"), {"yes", "partial", "no"})
            if item.get("verified") == "no":
                self.assertTrue(item.get("notes"), f"{eid} phai ghi ly do chua xac minh")

    def test_no_structural_problems(self) -> None:
        structural = check.structural_issues(self.parts, self.external, self.bom)
        self.assertEqual(structural, [])

    def test_critical_bom_mpns_are_registered(self) -> None:
        mpns = {p["mpn"] for p in self.parts.values()}
        mpns |= {e["mpn"] for e in self.external.values() if e.get("mpn")}
        for row in self.bom:
            if row["dnp"] != "no" or row["block"] not in check.CRITICAL_BLOCKS:
                continue
            if row["verify"] == "not-chosen":
                continue
            self.assertIn(row["mpn"], mpns, f"{row['ref']} thieu trong so linh kien")

    def test_no_blockers_for_prototype(self) -> None:
        blockers = {issue.item for issue in self.issues if issue.level == "blocker"}
        self.assertEqual(blockers, set())

    def test_pack_is_only_an_assumption(self) -> None:
        warnings = {issue.message for issue in self.issues if issue.level == "warn"}
        self.assertTrue(any("gia dinh" in message.lower() for message in warnings))

    def test_known_warnings_are_reported(self) -> None:
        warnings = {issue.item for issue in self.issues if issue.level == "warn"}
        for item in ("J1", "L1", "MODEM"):
            self.assertIn(item, warnings)

    def test_buck_vset_is_resolved(self) -> None:
        blockers = {issue.item for issue in self.issues if issue.level == "blocker"}
        self.assertNotIn("U2", blockers)
        self.assertEqual(
            [row["mpn"] for row in self.bom if row["ref"] == "R13"],
            ["RC0603FR-07267KL"],
        )

    def test_report_renders_blockers(self) -> None:
        text = check.render()
        self.assertIn("## 1. Linh kiện chính", text)
        self.assertIn("## 3. Vấn đề phát hiện", text)
        self.assertIn("| warn |", text)
        self.assertIn("gia dinh", text.lower())
        self.assertIn("TPS61088RHLR", text)

    def test_check_mode_passes(self) -> None:
        self.assertEqual(check.main(["--check"]), 0)

    def test_strict_mode_passes_with_assumptions(self) -> None:
        self.assertEqual(check.main(["--strict"]), 0)

    def test_production_mode_fails_until_docs(self) -> None:
        self.assertEqual(check.main(["--production"]), 1)

    def test_non_strict_mode_passes(self) -> None:
        self.assertEqual(check.main([]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
