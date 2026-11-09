"""Test hàng đợi uplink bền, ưu tiên và backoff."""

from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex.uplink import UplinkError, UplinkQueue


class UplinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "queue.jsonl"
        self.clock = FakeClock()
        self.queue = self._make()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make(self, **kwargs) -> UplinkQueue:
        params = {
            "max_bytes": 256 * 1024,
            "max_attempts": 4,
            "base_delay_s": 2.0,
            "max_delay_s": 20.0,
            "jitter": 0.0,
            "rng": random.Random(7),
        }
        params.update(kwargs)
        return UplinkQueue(self.path, self.clock, **params)

    def _enqueue(self, queue: UplinkQueue, payload: dict, priority: str) -> str:
        queue.enqueue(payload, priority)
        pending = queue.pending_ids()
        self.assertTrue(pending, "bản tin phải nằm trong hàng đợi")
        return pending[-1]

    def test_ids_are_16_hex_and_unique(self) -> None:
        first = self._enqueue(self.queue, {"type": "status"}, "status")
        second = self._enqueue(self.queue, {"type": "status"}, "status")
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertRegex(second, r"^[0-9a-f]{16}$")
        self.assertNotEqual(first, second, "bản tin trùng nội dung vẫn phải có id riêng")

    def test_explicit_id_is_deduped(self) -> None:
        message = {"type": "motion", "id": "0123456789abcdef"}
        self.queue.enqueue(message, "motion")
        self.queue.enqueue(dict(message), "motion")
        self.assertEqual(len(self.queue), 1)

    def test_persisted_as_jsonl(self) -> None:
        self.queue.enqueue({"type": "battery", "mv": 3300}, "battery")
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertIn("id", record["msg"])

    def test_priority_order(self) -> None:
        self._enqueue(self.queue, {"type": "battery"}, "battery")
        self._enqueue(self.queue, {"type": "status"}, "status")
        self._enqueue(self.queue, {"type": "motion"}, "motion")
        self._enqueue(self.queue, {"type": "fault"}, "fault")
        order = []
        for _ in range(4):
            message = self.queue.peek(self.clock.now())
            self.assertIsNotNone(message)
            order.append(message["type"])
            self.queue.mark_sent(message["id"])
        self.assertEqual(order, ["fault", "motion", "status", "battery"])

    def test_mark_sent_removes_and_is_idempotent(self) -> None:
        message_id = self._enqueue(self.queue, {"type": "status"}, "status")
        self.assertTrue(self.queue.mark_sent(message_id))
        self.assertEqual(len(self.queue), 0)
        self.assertFalse(self.queue.mark_sent(message_id))

    def test_retry_delays_message(self) -> None:
        message_id = self._enqueue(self.queue, {"type": "motion"}, "motion")
        delay = self.queue.retry_later(message_id, "network down")
        self.assertIsNotNone(delay)
        self.assertIsNone(self.queue.peek(self.clock.now()))
        self.clock.advance(1.0)
        self.assertIsNone(self.queue.peek(self.clock.now()))
        self.clock.advance(float(delay) + 0.5)
        self.assertIsNotNone(self.queue.peek(self.clock.now()))

    def test_backoff_grows_and_caps(self) -> None:
        message_id = self._enqueue(self.queue, {"type": "motion"}, "motion")
        delays: list[float] = []
        for _ in range(3):
            delay = self.queue.retry_later(message_id, "boom")
            self.assertIsNotNone(delay)
            delays.append(float(delay))
            self.clock.advance(float(delay) + 0.1)
        self.assertGreater(delays[1], delays[0])
        self.assertLessEqual(max(delays), 20.0, "phải có trần backoff")

    def test_max_attempts_drops_message(self) -> None:
        message_id = self._enqueue(self.queue, {"type": "motion"}, "motion")
        for _ in range(4):
            self.queue.retry_later(message_id, "boom")
            self.clock.advance(30.0)
        self.assertEqual(len(self.queue), 0)
        self.assertGreaterEqual(self.queue.stats()["dropped"], 1)

    def test_restart_keeps_pending(self) -> None:
        first = self._enqueue(self.queue, {"type": "motion"}, "motion")
        second = self._enqueue(self.queue, {"type": "status"}, "status")
        reopened = self._make()
        self.assertEqual(reopened.pending_ids(), [first, second])
        self.assertEqual(len(reopened), 2)

    def test_restart_does_not_resend_acked(self) -> None:
        message_id = self._enqueue(self.queue, {"type": "motion"}, "motion")
        self.queue.mark_sent(message_id)
        reopened = self._make()
        self.assertEqual(len(reopened), 0)
        self.assertEqual(reopened.pending_ids(), [])

    def test_overflow_drops_lowest_priority(self) -> None:
        small = self._make(max_bytes=900)
        small.enqueue({"type": "fault", "detail": "x" * 100}, "fault")
        for _ in range(20):
            small.enqueue({"type": "temp", "detail": "y" * 100}, "temp")
        stats = small.stats()
        self.assertGreater(stats["dropped"], 0)
        self.assertLessEqual(len(small), 6)
        remaining = small.peek(self.clock.now())
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining["type"], "fault")
        self.assertLessEqual(stats["bytes"], stats["max_bytes"])

    def test_corrupt_lines_are_skipped(self) -> None:
        self._enqueue(self.queue, {"type": "status"}, "status")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("not json at all\n")
            handle.write("\n")
        reopened = self._make()
        self.assertEqual(len(reopened), 1)
        self.assertGreaterEqual(reopened.stats()["corrupt_lines"], 1)

    def test_unknown_priority_rejected(self) -> None:
        with self.assertRaises(UplinkError):
            self.queue.enqueue({"type": "status"}, "urgent")

    def test_invalid_explicit_id_rejected(self) -> None:
        with self.assertRaises(UplinkError):
            self.queue.enqueue({"type": "status", "id": "ABC"}, "status")


if __name__ == "__main__":
    unittest.main(verbosity=2)
