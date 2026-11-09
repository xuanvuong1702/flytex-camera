"""Kiểm tra dữ liệu modem EC200U và pack LFP đề xuất."""

from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(path: str) -> dict:
    with (ROOT / path).open("rb") as handle:
        return tomllib.load(handle)


class ModemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load("spec/modem/ec200u.toml")
        cls.pins = {int(pin["num"]): pin for pin in cls.data["pins"]}

    def test_ri_pin_is_62(self) -> None:
        self.assertEqual(self.data["ri_pin"], 62)
        self.assertEqual(self.pins[62]["name"], "MAIN_RI")

    def test_usb_and_uart_pins(self) -> None:
        self.assertEqual(self.pins[69]["name"], "USB_DP")
        self.assertEqual(self.pins[70]["name"], "USB_DM")
        self.assertEqual(self.pins[67]["name"], "MAIN_TXD")
        self.assertEqual(self.pins[68]["name"], "MAIN_RXD")

    def test_sim_pins(self) -> None:
        for num in (14, 15, 16, 17):
            self.assertIn("USIM", self.pins[num]["name"])

    def test_power_range_documented(self) -> None:
        self.assertIn("3,3-4,3", " ".join(pin.get("note", "") for pin in self.pins.values()))


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load("spec/pack/lfp-15ah.toml")

    def test_cell_capacity(self) -> None:
        self.assertEqual(self.data["cell"]["capacity_ah"], 15.0)
        self.assertEqual(self.data["cell"]["nominal_v"], 3.2)

    def test_bms_requirements(self) -> None:
        self.assertGreaterEqual(self.data["bms"]["continuous_a"], 8.0)
        self.assertLessEqual(self.data["bms"]["quiescent_ua_max"], 100.0)
        self.assertIn("10 kOhm", self.data["bms"]["ntc"])
        # Boost 5 V: 5,56 A trung binh, 6,52 A dinh o 3,0 V; BMS phai du.
        self.assertGreaterEqual(self.data["bms"]["discharge_peak_a"], 6.52 * 1.2)

    def test_docs_still_pending_but_prototype_allowed(self) -> None:
        self.assertFalse(self.data["pack"]["docs_ready"])
        self.assertTrue(self.data["pack"]["prototype_allowed"])
        self.assertGreater(self.data["pack"]["assumed_bms_quiescent_ua"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)