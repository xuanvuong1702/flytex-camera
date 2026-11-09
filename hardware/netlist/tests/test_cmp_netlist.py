"""Test netlist pin-level CMP."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.netlist import cmp as netlist  # noqa: E402


class CmpNetlistTests(unittest.TestCase):
    def test_components_exist(self) -> None:
        refs = {component.ref for component in netlist.COMPONENTS}
        self.assertTrue({"J1", "U1", "J2", "J3", "J4", "U2"} <= refs)

    def test_no_erc_errors(self) -> None:
        self.assertEqual(netlist.validate(), [])

    def test_camera_has_no_pwdn(self) -> None:
        camera = next(
            component for component in netlist.COMPONENTS if component.ref == "J2"
        )
        names = {pin.name for pin in camera.pins}
        self.assertNotIn("PWDN", names)
        self.assertEqual(len(camera.pins), 20)

    def test_soc_pins_are_from_documented_set(self) -> None:
        documented = netlist._known_core_pins()
        for component in netlist.COMPONENTS:
            if component.ref != "U1":
                continue
            for pin in component.pins:
                self.assertIn(pin.num, documented)

    def test_usb_mux_topology(self) -> None:
        mux = next(component for component in netlist.COMPONENTS if component.ref == "U2")
        nets = {pin.num: pin.net for pin in mux.pins}
        self.assertEqual(nets["8"], "USB_DP")
        self.assertEqual(nets["7"], "USB_DM")
        self.assertEqual(nets["1"], "MODEM_USB_DP")
        self.assertEqual(nets["3"], "SVC_USB_DP")
        self.assertEqual(nets["9"], "USB_SEL")

    def test_markdown_and_csv(self) -> None:
        text = netlist.MD.read_text(encoding="utf-8")
        self.assertIn("## 2. Net", text)
        self.assertIn("U1", netlist.CSV.read_text(encoding="utf-8"))

    def test_every_ref_is_in_bom(self) -> None:
        import csv

        refs = {row["ref"] for row in csv.DictReader(
            netlist.BOM.open(encoding="utf-8", newline="")
        )}
        for component in netlist.COMPONENTS:
            self.assertIn(component.ref, refs)

    def test_check_mode_passes(self) -> None:
        self.assertEqual(netlist.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
