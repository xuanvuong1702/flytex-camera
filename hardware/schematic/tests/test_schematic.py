"""Test schematic khối: net, ERC, SVG."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.schematic import render  # noqa: E402


class SchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = render.load()
        cls.issues = render.validate(cls.data)

    def test_two_sheets(self) -> None:
        self.assertEqual([sheet["id"] for sheet in self.data["sheets"]], ["pwr", "cmp"])
        self.assertEqual(sum(len(sheet["blocks"]) for sheet in self.data["sheets"]), 21)

    def test_erc_has_no_errors(self) -> None:
        errors = [message for level, message in self.issues if level == "error"]
        self.assertEqual(errors, [])

    def test_no_open_tbd_net(self) -> None:
        warnings = [message for level, message in self.issues if level == "warn"]
        self.assertEqual(warnings, [])

    def test_b2b_on_both_sheets(self) -> None:
        for sheet in self.data["sheets"]:
            self.assertTrue(any(block["id"] == "B2B" for block in sheet["blocks"]))

    def test_power_nets_have_at_least_two_ends(self) -> None:
        for sheet in self.data["sheets"]:
            for block in sheet["blocks"]:
                for pin in block["pins"]:
                    if pin["net"] in render.POWER_NETS:
                        self.assertTrue(pin["net"].strip())

    def test_uart_is_not_short_tx_to_tx(self) -> None:
        nets = {
            pin["net"]
            for sheet in self.data["sheets"]
            for block in sheet["blocks"]
            for pin in block["pins"]
        }
        self.assertIn("UART_MCU_TX", nets)
        self.assertIn("UART_SOC_TX", nets)
        self.assertNotIn("UART_TX", nets)  # net gộp TX cũ đã bị loại

    def test_svg_is_valid_xml(self) -> None:
        for path, _ in (("pwr", None), ("cmp", None)):
            svg = render.OUT_DIR / f"{path}-blocks.svg"
            root = ET.parse(svg).getroot()
            self.assertTrue(root.tag.endswith("svg"))

    def test_check_mode_passes(self) -> None:
        self.assertEqual(render.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
