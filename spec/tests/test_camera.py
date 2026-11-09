"""Kiểm tra pinout camera SC3336 3MP (B) nhập từ bản vẽ Luckfox."""

from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = ROOT / "spec" / "camera" / "sc3336-b.toml"


class CameraPinoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with SPEC.open("rb") as handle:
            cls.data = tomllib.load(handle)
        cls.pins = {int(pin["num"]): pin for pin in cls.data["pins"]}

    def test_twenty_pins_numbered(self) -> None:
        self.assertEqual(sorted(self.pins), list(range(1, 21)))

    def test_power_on_pins_19_20(self) -> None:
        for number in (19, 20):
            self.assertEqual(self.pins[number]["net"], "+3V3")
            self.assertEqual(self.pins[number]["name"], "+3.3V")

    def test_i2c_and_reset(self) -> None:
        self.assertEqual(self.pins[13]["net"], "CAM_SCL")
        self.assertEqual(self.pins[14]["net"], "CAM_SDA")
        self.assertEqual(self.pins[16]["net"], "CAM_RST")

    def test_mipi_lanes(self) -> None:
        nets = {pin["net"] for pin in self.pins.values()}
        for net in ("MIPI_CLKP", "MIPI_CLKN", "MIPI_D0P", "MIPI_D0N", "MIPI_D1P", "MIPI_D1N"):
            self.assertIn(net, nets)

    def test_ground_pins(self) -> None:
        grounds = [num for num, pin in self.pins.items() if pin["net"] == "GND"]
        self.assertGreaterEqual(len(grounds), 7)

    def test_source_recorded(self) -> None:
        self.assertIn("luckfox.com", self.data["source"])
        self.assertIn("20", self.data["connector"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
