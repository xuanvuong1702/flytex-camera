"""Test đồng hồ và lớp giao tiếp MCU (MemoryMcu)."""

from __future__ import annotations

import unittest

try:
    from _helpers import FakeClock, make_mcu
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock, make_mcu

from flytex import regs_gen
from flytex.mcu import McuNack, ProtocolMismatch


class FakeClockTests(unittest.TestCase):
    def test_starts_at_zero(self) -> None:
        clock = FakeClock()
        self.assertEqual(clock.now(), 0.0)
        self.assertEqual(clock.monotonic(), 0.0)

    def test_advance_moves_both_clocks(self) -> None:
        clock = FakeClock(start=100.0)
        clock.advance(2.5)
        self.assertAlmostEqual(clock.monotonic(), 2.5)
        self.assertAlmostEqual(clock.now(), 102.5)

    def test_sleep_is_advance(self) -> None:
        clock = FakeClock()
        clock.sleep(3.0)
        self.assertAlmostEqual(clock.monotonic(), 3.0)

    def test_set_now_does_not_move_monotonic(self) -> None:
        clock = FakeClock()
        clock.advance(1.0)
        clock.set_now(500.0)
        self.assertAlmostEqual(clock.now(), 500.0)
        self.assertAlmostEqual(clock.monotonic(), 1.0)

    def test_monotonic_never_goes_back(self) -> None:
        clock = FakeClock()
        clock.advance(5.0)
        clock.sleep(0.0)
        self.assertGreaterEqual(clock.monotonic(), 5.0)


class McuClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client, self.memory, self.clock = make_mcu()

    def test_protocol_version(self) -> None:
        self.client.check_protocol()
        self.assertEqual(self.client.proto_version, "1.1")
        self.assertEqual(self.client.proto_major, 1)

    def test_wrong_major_rejected(self) -> None:
        client, _, _ = make_mcu(proto_ver=0x21)
        with self.assertRaises(ProtocolMismatch):
            client.check_protocol()

    def test_status_defaults(self) -> None:
        status = self.client.status()
        self.assertFalse(status["SOC_READY"])
        self.assertFalse(status["SOC_POWER_ON"])

    def test_event_clears_on_read(self) -> None:
        self.memory.raise_event("PIR")
        self.assertEqual(self.client.events(), {"PIR"})
        self.assertEqual(self.client.events(), set())

    def test_multiple_events(self) -> None:
        self.memory.raise_event({"PIR", "VBUS_CHANGE"})
        self.assertEqual(self.client.events(), {"PIR", "VBUS_CHANGE"})

    def test_battery_round_trip(self) -> None:
        self.memory.set_battery_mv(3300)
        self.assertEqual(self.client.battery_mv(), 3300)
        self.memory.set_battery_mv(2400)
        self.assertEqual(self.client.battery_mv(), 2400)

    def test_temperature_invalid_is_none(self) -> None:
        batt, amb = self.client.temps()
        self.assertIsNone(batt)
        self.assertIsNone(amb)

    def test_temperature_values(self) -> None:
        self.memory.set_temps(25, -5)
        self.assertEqual(self.client.temps(), (25, -5))

    def test_mode_round_trip(self) -> None:
        self.assertEqual(self.client.mode(), "eco")
        self.client.set_mode("watch")
        self.assertEqual(self.client.mode(), "watch")

    def test_invalid_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.client.set_mode("sleepy")

    def test_wake_in_round_trip(self) -> None:
        self.client.set_wake_in_s(3600)
        self.assertEqual(self.client.wake_in_s(), 3600)

    def test_wake_channel_round_trip(self) -> None:
        self.client.set_wake_chan("sms")
        self.assertEqual(self.client.wake_chan(), "sms")

    def test_fault_code(self) -> None:
        self.assertEqual(self.client.fault(), "NONE")
        self.memory.set_fault("BATT_OVERTEMP")
        self.assertEqual(self.client.fault(), "BATT_OVERTEMP")

    def test_write_read_only_nacked(self) -> None:
        with self.assertRaises(McuNack):
            self.client._write("PROTO_VER", b"\x00")

    def test_out_of_range_nacked(self) -> None:
        with self.assertRaises(McuNack):
            self.client._link.read(0x7F, 1)

    def test_command_recorded(self) -> None:
        self.client.cmd("MODEM_ON")
        self.assertIn("MODEM_ON", self.memory.commands)

    def test_invalid_command_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.client.cmd("DO_THE_THING")

    def test_uptime_and_boot_count(self) -> None:
        self.memory.set_uptime_s(1234)
        self.memory.set_boot_count(7)
        self.assertEqual(self.client.uptime_s(), 1234)
        self.assertEqual(self.client.boot_count(), 7)

    def test_regmap_spec_is_single_source(self) -> None:
        # App không được có bảng riêng: mọi địa chỉ lấy từ file sinh.
        self.assertEqual(regs_gen.REG_BY_NAME["EVENT"].addr, 0x04)
        self.assertEqual(regs_gen.REG_BY_NAME["WAKE_CHAN"].addr, 0x12)
        self.assertEqual(regs_gen.I2C_ADDR, 0x30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
