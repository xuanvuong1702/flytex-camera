"""Test máy trạng thái nguồn của ứng dụng."""

from __future__ import annotations

import unittest

try:
    from _helpers import FakeRecorder, FakeUplink, make_mcu
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeRecorder, FakeUplink, make_mcu

from flytex.power import Busy, PowerConfig, PowerController


class PowerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client, self.memory, self.clock = make_mcu()
        self.recorder = FakeRecorder(self.clock)
        self.uplink = FakeUplink()
        self.controller = PowerController(
            self.client,
            self.clock,
            self.recorder,
            self.uplink,
            PowerConfig(clip_s=5.0, settle_s=2.0, live_s=4.0, mode="eco"),
        )

    def _tick(self) -> None:
        self.controller.tick(self.clock.now())

    def test_starts_in_eco(self) -> None:
        self.assertEqual(self.controller.state.value, "s0")
        self.assertEqual(self.controller.mode, "eco")

    def test_starts_in_watch_when_configured(self) -> None:
        controller = PowerController(
            self.client,
            self.clock,
            self.recorder,
            self.uplink,
            PowerConfig(mode="watch"),
        )
        self.assertEqual(controller.state.value, "s1")

    def test_pir_starts_recording(self) -> None:
        self.memory.raise_event("PIR")
        self._tick()
        self.assertEqual(self.controller.state.value, "s2")
        self.assertTrue(self.recorder.recording)
        self.assertRegex(self.controller.clip_id or "", r"^[0-9a-f]{16}$")

    def test_clip_finishes_and_enqueues_motion(self) -> None:
        self.memory.raise_event("PIR")
        self._tick()
        self.clock.advance(5.5)
        self._tick()
        self.assertFalse(self.recorder.recording)
        self.assertIn("motion", self.uplink.types())

    def test_returns_to_eco_after_clip(self) -> None:
        self.memory.raise_event("PIR")
        self._tick()
        self.clock.advance(5.5)
        self._tick()
        self.assertEqual(self.controller.state.value, "s2")
        self.clock.advance(2.5)
        self._tick()
        self.assertEqual(self.controller.state.value, "s0")

    def test_returns_to_watch_after_clip(self) -> None:
        controller = PowerController(
            self.client,
            self.clock,
            self.recorder,
            self.uplink,
            PowerConfig(clip_s=5.0, settle_s=2.0, mode="watch"),
        )
        self.memory.raise_event("PIR")
        controller.tick(self.clock.now())
        self.clock.advance(5.5)
        controller.tick(self.clock.now())
        self.clock.advance(2.5)
        controller.tick(self.clock.now())
        self.assertEqual(controller.state.value, "s1")

    def test_live_enters_s3_and_returns(self) -> None:
        self.controller.request_live(4.0)
        self.assertEqual(self.controller.state.value, "s3")
        self.clock.advance(4.5)
        self._tick()
        self.assertEqual(self.controller.state.value, "s2")
        # Clip vẫn đang ghi tới clip_s rồi mới nghỉ settle_s.
        self.clock.advance(2.5)
        self._tick()
        self.assertEqual(self.controller.state.value, "s2")
        self.clock.advance(2.5)
        self._tick()
        self.assertEqual(self.controller.state.value, "s0")

    def test_live_remaining_decreases(self) -> None:
        self.controller.request_live(10.0)
        before = self.controller.live_remaining_s(self.clock.now())
        self.clock.advance(3.0)
        after = self.controller.live_remaining_s(self.clock.now())
        self.assertAlmostEqual(before - after, 3.0)

    def test_mode_change_rejected_while_recording(self) -> None:
        self.memory.raise_event("PIR")
        self._tick()
        with self.assertRaises(Busy):
            self.controller.set_mode("watch")

    def test_invalid_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.set_mode("sleepy")

    def test_fault_enters_and_leaves(self) -> None:
        self.memory.set_fault("BATT_OVERTEMP")
        self._tick()
        self.assertEqual(self.controller.state.value, "sf")
        self.assertIn("fault", self.uplink.types())
        self.memory.set_fault("NONE")
        self._tick()
        self.assertEqual(self.controller.state.value, "s0")

    def test_shutdown_request_closes_and_acks(self) -> None:
        self.memory.raise_event("PIR")
        self._tick()
        self.memory.raise_event("SHUTDOWN_REQ")
        self._tick()
        self.assertTrue(self.controller.shutdown_requested)
        self.assertTrue(self.controller.shutdown_done)
        self.assertFalse(self.recorder.recording)
        self.assertIn("SOC_SHUTDOWN_DONE", self.memory.commands)
        self.assertIn("shutdown", self.uplink.types())

    def test_low_battery_triggers_safe_shutdown(self) -> None:
        self.memory.set_status("LOW_BATT", True)
        self.memory.raise_event("LOW_BATT")
        self._tick()
        self.assertTrue(self.controller.shutdown_requested)
        self.assertTrue(self.controller.shutdown_done)
        self.assertIn("shutdown", self.uplink.types())

    def test_request_live_after_shutdown_rejected(self) -> None:
        self.memory.raise_event("SHUTDOWN_REQ")
        self._tick()
        with self.assertRaises(Busy):
            self.controller.request_live(5.0)

    def test_tick_is_idempotent_after_shutdown(self) -> None:
        self.memory.raise_event("SHUTDOWN_REQ")
        self._tick()
        sent = list(self.memory.commands)
        self._tick()
        self.assertEqual(self.memory.commands, sent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
