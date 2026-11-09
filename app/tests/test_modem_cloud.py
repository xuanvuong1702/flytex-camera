"""Test modem AT, cloud trong bộ nhớ, nguồn hình giả và chẩn đoán."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex.cloud import CloudError, MemoryBus, topic_matches
from flytex.diagnostics import Diagnostics, DiagnosticsError
from flytex.media import FakeSource, MediaError, RkMpiSource
from flytex.modem import AtClient, AtError, AtTimeout, FakeModem


class ModemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.fake = FakeModem(self.clock)
        self.urcs: list[str] = []
        self.client = AtClient(
            self.fake,
            self.clock,
            on_urc=self.urcs.append,
            pwrkey=self.fake,
        )

    def test_power_on_and_off(self) -> None:
        self.client.power_on(timeout=2.0)
        self.assertTrue(self.client.powered)
        self.assertTrue(self.client.ready)
        self.client.power_off(timeout=2.0)
        self.assertFalse(self.client.powered)

    def test_signal_dbm(self) -> None:
        self.client.power_on(timeout=2.0)
        dbm = self.client.signal_dbm()
        self.assertIsInstance(dbm, int)
        self.assertLessEqual(dbm, -50)
        self.assertGreaterEqual(dbm, -115)

    def test_registration(self) -> None:
        self.client.power_on(timeout=2.0)
        info = self.client.registration()
        self.assertIn("registered", info)
        self.assertTrue(info["registered"])

    def test_error_response_raises(self) -> None:
        self.client.power_on(timeout=2.0)
        self.fake.set_response("AT+XYZ", ["ERROR"])
        with self.assertRaises(AtError):
            self.client.command("AT+XYZ")

    def test_timeout_is_real_and_advances_clock(self) -> None:
        self.client.power_on(timeout=2.0)
        self.fake.hang("AT+CSQ", True)
        before = self.clock.monotonic()
        with self.assertRaises(AtTimeout) as ctx:
            self.client.command("AT+CSQ", timeout=0.3)
        self.assertGreaterEqual(self.clock.monotonic() - before, 0.3)
        self.assertIn("AT+CSQ", str(ctx.exception))

    def test_urc_is_dispatched_not_returned(self) -> None:
        self.client.power_on(timeout=2.0)
        self.fake.inject_urc('+CMTI: "SM",1')
        result = self.client.command("AT", timeout=1.0)
        self.assertIn('+CMTI: "SM",1', self.urcs)
        self.assertFalse(any("CMTI" in line for line in result))

    def test_pending_urcs_are_kept(self) -> None:
        self.client.power_on(timeout=2.0)
        self.fake.inject_urc("+CREG: 1")
        self.client.command("AT", timeout=1.0)
        self.assertIn("+CREG: 1", self.client.pending_urcs())

    def test_sms_send_returns_reference(self) -> None:
        self.client.power_on(timeout=2.0)
        reference = self.client.sms_send("+84900000000", "W token", timeout=2.0)
        self.assertTrue(reference is None or isinstance(reference, int))

    def test_tcp_open(self) -> None:
        self.client.power_on(timeout=2.0)
        connect_id = self.client.tcp_open("example.com", 1883, timeout=2.0)
        self.assertEqual(connect_id, 0)


class CloudTests(unittest.TestCase):
    def test_topic_matches(self) -> None:
        self.assertTrue(topic_matches("dev/+/evt", "dev/abc/evt"))
        self.assertFalse(topic_matches("dev/+/evt", "dev/abc/status"))
        self.assertTrue(topic_matches("dev/#", "dev/abc/status"))
        self.assertFalse(topic_matches("dev/+/evt", "dev/a/b/evt"))

    def test_invalid_filter_rejected(self) -> None:
        with self.assertRaises((CloudError, ValueError)):
            topic_matches("dev/#/evt", "dev/a/evt")

    def test_publish_and_subscribe(self) -> None:
        bus = MemoryBus()
        received: list[tuple[str, bytes]] = []
        bus.subscribe("dev/+/evt", lambda topic, payload: received.append((topic, payload)))
        pub = bus.publisher()
        pub.connect()
        pub.publish("dev/abc/evt", b"hello", qos=1)
        self.assertEqual(received, [("dev/abc/evt", b"hello")])

    def test_retained_status(self) -> None:
        bus = MemoryBus()
        pub = bus.publisher()
        pub.connect()
        pub.publish("dev/abc/status", b"online", qos=1, retain=True)
        self.assertEqual(bus.retained("dev/abc/status"), b"online")

    def test_publish_when_disconnected_raises(self) -> None:
        bus = MemoryBus()
        pub = bus.publisher()
        with self.assertRaises(CloudError):
            pub.publish("dev/abc/evt", b"x")

    def test_messages_of_records_history(self) -> None:
        bus = MemoryBus()
        pub = bus.publisher()
        pub.connect()
        pub.publish("dev/abc/evt", b"one")
        pub.publish("dev/abc/evt", b"two")
        self.assertEqual(bus.messages_of("dev/abc/evt"), [b"one", b"two"])


class MediaTests(unittest.TestCase):
    def test_fake_source_is_deterministic(self) -> None:
        clock = FakeClock()
        source = FakeSource(clock, fps=10.0, payload_size=8)
        source.start()
        first = source.read_frame(0.0)
        clock.advance(0.2)
        second = source.read_frame(0.0)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None and second is not None
        self.assertGreaterEqual(len(first[1]), 8)
        self.assertGreater(second[0], first[0])
        source.stop()
        self.assertFalse(source.started)

    def test_frame_before_start_raises(self) -> None:
        source = FakeSource(FakeClock())
        with self.assertRaises(MediaError):
            source.read_frame(0.0)

    def test_real_camera_source_is_not_faked(self) -> None:
        with self.assertRaises(NotImplementedError):
            RkMpiSource().start()


class DiagnosticsTests(unittest.TestCase):
    def test_boot_count_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            diagnostics = Diagnostics(tmp, clock)
            self.assertEqual(diagnostics.record_boot("por"), 1)
            self.assertEqual(diagnostics.record_boot("wdt"), 2)
            reopened = Diagnostics(tmp, clock)
            self.assertEqual(reopened.boot_count, 2)
            self.assertEqual(reopened.last_boot_reason, "wdt")

    def test_shutdown_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = Diagnostics(tmp, FakeClock())
            diagnostics.record_shutdown("low_batt", 2900)
            reopened = Diagnostics(tmp, FakeClock())
            self.assertEqual(reopened.last_shutdown_reason, "low_batt")
            self.assertEqual(reopened.last_battery_mv, 2900)

    def test_log_rotation_keeps_file_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = Diagnostics(tmp, FakeClock(), max_bytes=1024)
            for index in range(80):
                diagnostics.log("info", f"dong log thu {index} " + "x" * 40)
            size = Path(tmp, "flytex.log").stat().st_size
            self.assertLessEqual(size, 1024)
            self.assertGreaterEqual(diagnostics.rotations, 1)
            self.assertIn("dong log", diagnostics.read_log())

    def test_invalid_log_level_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = Diagnostics(tmp, FakeClock())
            with self.assertRaises((DiagnosticsError, ValueError)):
                diagnostics.log("fatal", "x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
