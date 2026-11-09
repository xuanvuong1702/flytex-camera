"""Test bộ ghi clip: đoạn, chỉ mục, phục hồi sau mất điện, vòng ghi."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex.recorder import ClipInfo, RawMuxer, RecorderError, SegmentRecorder

CLIP_A = "0123456789abcdef"
CLIP_B = "fedcba9876543210"
CLIP_C = "0011223344556677"


class RecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = FakeClock()
        self.recorder = self._make()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make(self, **kwargs) -> SegmentRecorder:
        params = {
            "segment_s": 10.0,
            "max_bytes": 4 * 1024 * 1024,
            "pin_budget_bytes": 1024 * 1024,
            "segment_max_bytes": 4096,
        }
        params.update(kwargs)
        return SegmentRecorder(self.root, self.clock, RawMuxer(), **params)

    def _record(self, recorder: SegmentRecorder, clip_id: str, size: int = 100) -> ClipInfo:
        recorder.start(clip_id)
        for index in range(3):
            self.clock.advance(1.0)
            recorder.write(float(index), b"x" * size)
        return recorder.stop()

    def test_raw_muxer_rejected_when_disallowed(self) -> None:
        with self.assertRaises(RecorderError):
            self._make(allow_raw_muxer=False)

    def test_clip_ids_are_validated(self) -> None:
        with self.assertRaises(RecorderError):
            self.recorder.start("abc")
        with self.assertRaises(RecorderError):
            self.recorder.start("0123456789ABCDEF")

    def test_start_stop_creates_clip(self) -> None:
        info = self._record(self.recorder, CLIP_A)
        self.assertEqual(info.clip_id, CLIP_A)
        self.assertGreater(info.size_b, 0)
        clip_dir = Path(info.path)
        self.assertTrue(clip_dir.exists())
        self.assertTrue(info.segments)
        for name in info.segments:
            self.assertTrue((clip_dir / name).exists(), f"thiếu {name}")

    def test_write_without_start_raises(self) -> None:
        with self.assertRaises(RecorderError):
            self.recorder.write(0.0, b"data")

    def test_duplicate_clip_id_rejected(self) -> None:
        self._record(self.recorder, CLIP_A)
        with self.assertRaises(RecorderError):
            self.recorder.start(CLIP_A)

    def test_stop_without_start_raises(self) -> None:
        with self.assertRaises(RecorderError):
            self.recorder.stop()

    def test_index_is_jsonl_and_lists_clips(self) -> None:
        self._record(self.recorder, CLIP_A)
        self.clock.advance(1.0)
        self._record(self.recorder, CLIP_B)
        lines = self.recorder.index_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertTrue(lines)
        for line in lines:
            json.loads(line)
        ids = [clip.clip_id for clip in self.recorder.list_clips()]
        self.assertEqual(ids, [CLIP_A, CLIP_B])

    def test_new_instance_sees_previous_clips(self) -> None:
        self._record(self.recorder, CLIP_A)
        reopened = self._make()
        self.assertIsNotNone(reopened.clip(CLIP_A))

    def test_segments_rotate_by_size(self) -> None:
        recorder = self._make(segment_max_bytes=64)
        recorder.start(CLIP_A)
        for index in range(10):
            self.clock.advance(0.5)
            recorder.write(float(index), b"y" * 40)
        info = recorder.stop()
        self.assertGreater(len(info.segments), 1)

    def test_recover_removes_orphan_part_files(self) -> None:
        # Giả lập tàn dư của lần mất điện: file .part còn lại trong thư mục clip.
        orphan_dir = self.root / CLIP_A
        orphan_dir.mkdir()
        orphan = orphan_dir / "seg-00000.raw.part"
        orphan.write_bytes(b"partial")
        reopened = self._make()
        report = reopened.recover()
        self.assertTrue(report.removed_parts)
        self.assertFalse(list(self.root.rglob("*.part")))
        self.assertFalse(orphan.exists())

    def test_recover_repairs_truncated_index(self) -> None:
        self._record(self.recorder, CLIP_A)
        with self.recorder.index_path.open("a", encoding="utf-8") as fh:
            fh.write('{"broken": ')
        reopened = self._make()
        report = reopened.recover()
        self.assertEqual([clip.clip_id for clip in reopened.list_clips()], [CLIP_A])
        self.assertGreaterEqual(report.dropped_index_lines, 1)

    def test_pin_protects_old_clip_from_capacity_eviction(self) -> None:
        first = self._record(self.recorder, CLIP_A)
        self.clock.advance(1.0)
        self._record(self.recorder, CLIP_B)
        self.clock.advance(1.0)
        self._record(self.recorder, CLIP_C)
        self.recorder.pin(first.clip_id)
        recorder = self._make(max_bytes=first.size_b * 2 + 10)
        recorder.recover()
        recorder.pin(first.clip_id)
        evicted = recorder.evict()
        remaining = {clip.clip_id for clip in recorder.list_clips()}
        self.assertIn(first.clip_id, remaining)
        self.assertTrue(evicted)

    def test_pin_unknown_clip_raises(self) -> None:
        with self.assertRaises(RecorderError):
            self.recorder.pin(CLIP_A)


if __name__ == "__main__":
    unittest.main(verbosity=2)
