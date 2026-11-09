"""Test netlist pin-level PWR."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.netlist import pwr  # noqa: E402


class NetlistTests(unittest.TestCase):
    def test_components_and_ic_pin_counts(self) -> None:
        refs = {component.ref: component for component in pwr.COMPONENTS}
        self.assertGreaterEqual(len(refs), 25)
        self.assertEqual(len(refs["U1"].pins), 11)
        self.assertEqual(len(refs["U2"].pins), 21)
        self.assertEqual(len(refs["U3"].pins), 9)
        self.assertEqual(len(refs["Q1"].pins), 6)
        self.assertEqual(len(refs["Q2"].pins), 6)

    def test_no_erc_errors(self) -> None:
        self.assertEqual(pwr.validate(), [])

    def test_every_net_has_two_ends(self) -> None:
        for net, ends in pwr.nets().items():
            self.assertGreaterEqual(len(ends), 2, net)

    def test_power_rails_have_sources(self) -> None:
        by_net = pwr.nets()
        for net, source in (
            ("+5V_BOOST", "U2"),
            ("+3V3", "U3"),
            ("+5V_SOC", "Q1"),
            ("+5V_MODEM", "Q2"),
        ):
            refs = {component.ref for component, _ in by_net[net]}
            self.assertIn(source, refs)

    def test_fsw_resistor_between_fsw_and_sw(self) -> None:
        r6 = next(component for component in pwr.COMPONENTS if component.ref == "R6")
        nets = {pin.net for pin in r6.pins}
        self.assertEqual(nets, {"FSW_BOOST", "SW_BOOST"})

    def test_markdown_and_csv_exist(self) -> None:
        self.assertIn("## 2. Net", pwr.MD.read_text(encoding="utf-8"))
        self.assertIn("U1", pwr.CSV.read_text(encoding="utf-8"),)
        self.assertIn("VBUS", pwr.CSV.read_text(encoding="utf-8"))

    def test_check_mode_passes(self) -> None:
        self.assertEqual(pwr.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
