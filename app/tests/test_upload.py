"""Test tải clip: PUT thật qua HTTP cục bộ và hàng đợi bền."""

from __future__ import annotations

import http.server
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex.upload import (
    FakeUploader,
    HttpUploader,
    UploadError,
    UploadSpool,
)


class _PutHandler(http.server.BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_PUT(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if "/fail/" in self.path:
            self.send_response(500)
            self.end_headers()
            return
        type(self).received.append(
            {
                "path": self.path,
                "body": body,
                "content_type": self.headers.get("Content-Type"),
                "clip_id": self.headers.get("X-Clip-Id"),
            }
        )
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args: object) -> None:  # tắt log
        return


class UploadHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.file = Path(self._tmp.name) / "clip.ts"
        self.file.write_bytes(b"0123456789" * 10)
        _PutHandler.received = []
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _PutHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}/clips/{{clip_id}}.ts"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def test_put_upload_success(self) -> None:
        uploader = HttpUploader(self.base, timeout=5.0, allow_insecure=True)
        result = uploader.upload(self.file, "0123456789abcdef")
        self.assertEqual(result.size_b, self.file.stat().st_size)
        self.assertTrue(result.url.endswith("/clips/0123456789abcdef.ts"))
        self.assertEqual(len(_PutHandler.received), 1)
        request = _PutHandler.received[0]
        self.assertEqual(request["body"], self.file.read_bytes())
        self.assertEqual(request["content_type"], "video/mp2t")
        self.assertEqual(request["clip_id"], "0123456789abcdef")

    def test_http_error_raises(self) -> None:
        host, port = self.server.server_address
        uploader = HttpUploader(f"http://{host}:{port}/fail/{{clip_id}}.ts", timeout=2.0, allow_insecure=True)
        with self.assertRaises(UploadError):
            uploader.upload(self.file, "0123456789abcdef")

    def test_connection_refused_raises(self) -> None:
        uploader = HttpUploader("http://127.0.0.1:1/c/{clip_id}", timeout=2.0, allow_insecure=True)
        with self.assertRaises(UploadError):
            uploader.upload(self.file, "0123456789abcdef")

    def test_missing_file_raises(self) -> None:
        uploader = HttpUploader(self.base, allow_insecure=True)
        with self.assertRaises(UploadError):
            uploader.upload(Path(self._tmp.name) / "khong-co.ts", "0123456789abcdef")

    def test_http_template_rejected(self) -> None:
        with self.assertRaises(ValueError):
            HttpUploader("http://example.com/{clip_id}")

    def test_template_requires_placeholder(self) -> None:
        with self.assertRaises(ValueError):
            HttpUploader("http://example.com/upload")

    def test_fake_uploader(self) -> None:
        uploader = FakeUploader(fail_times=1)
        with self.assertRaises(UploadError):
            uploader.upload(self.file, "0123456789abcdef")
        result = uploader.upload(self.file, "0123456789abcdef")
        self.assertEqual(result.clip_id, "0123456789abcdef")
        self.assertEqual(len(uploader.calls), 1)


class SpoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = FakeClock()
        self.spool = self._make()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make(self, **kwargs) -> UploadSpool:
        params = {"max_items": 5, "base_delay_s": 10.0, "max_delay_s": 60.0, "max_attempts": 3}
        params.update(kwargs)
        return UploadSpool(self.root / "upload.jsonl", self.clock, **params)

    def test_add_and_pending(self) -> None:
        self.assertTrue(self.spool.add("a" * 16, "/data/clip.ts", 100))
        self.assertFalse(self.spool.add("a" * 16, "/data/clip.ts", 100))
        item = self.spool.pending()
        self.assertIsNotNone(item)
        self.assertEqual(item.clip_id, "a" * 16)
        self.assertEqual(len(self.spool), 1)

    def test_done_removes_and_survives_restart(self) -> None:
        self.spool.add("a" * 16, "/data/a.ts", 100)
        self.spool.add("b" * 16, "/data/b.ts", 200)
        self.assertTrue(self.spool.done("a" * 16))
        reopened = self._make()
        self.assertEqual(reopened.pending_ids(), ["b" * 16])
        self.assertFalse(reopened.add("a" * 16, "/data/a.ts", 100))

    def test_fail_schedules_retry_with_backoff(self) -> None:
        self.spool.add("a" * 16, "/data/a.ts", 100)
        delay = self.spool.fail("a" * 16, "timeout")
        self.assertIsNotNone(delay)
        self.assertIsNone(self.spool.pending())
        self.clock.advance(float(delay) + 1.0)
        self.assertIsNotNone(self.spool.pending())
        second = self.spool.fail("a" * 16, "timeout")
        self.assertGreater(float(second), float(delay))

    def test_max_attempts_drops(self) -> None:
        self.spool.add("a" * 16, "/data/a.ts", 100)
        for _ in range(3):
            self.spool.fail("a" * 16, "x")
            self.clock.advance(120.0)
        self.assertEqual(len(self.spool), 0)
        self.assertEqual(self.spool.stats()["pending"], 0)

    def test_full_spool_raises(self) -> None:
        for index in range(5):
            self.spool.add(f"{index:016x}", "/data/x.ts", 1)
        with self.assertRaises(UploadError):
            self.spool.add("f" * 16, "/data/y.ts", 1)

    def test_corrupt_lines_are_skipped(self) -> None:
        self.spool.add("a" * 16, "/data/a.ts", 100)
        with (self.root / "upload.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("khong phai json\n")
        reopened = self._make()
        self.assertEqual(len(reopened), 1)
        self.assertGreaterEqual(reopened.corrupt_lines, 1)

    def test_stats(self) -> None:
        self.spool.add("a" * 16, "/data/a.ts", 100)
        stats = self.spool.stats()
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["due"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
