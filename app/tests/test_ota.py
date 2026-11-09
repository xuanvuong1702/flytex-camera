"""Test OTA: tải, xác minh chữ ký, A/B, quay lui."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex.ota import (
    STATE_ACTIVATING,
    STATE_FAILED,
    STATE_HEALTHY,
    STATE_ROLLED_BACK,
    STATE_STAGED,
    OtaError,
    OtaManager,
)


class FakeDownloader:
    def __init__(self, payload: bytes = b"image-bytes" * 100) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []
        self.fail = False

    def download(self, url: str, dest: Path, expected_size: int, timeout: float) -> int:
        if self.fail:
            raise OtaError("mang loi")
        self.calls.append((url, str(dest)))
        dest.write_bytes(self.payload)
        return len(self.payload)


class FakeVerifier:
    def __init__(self, accept: bool = True) -> None:
        self.accept = accept
        self.calls: list[tuple[str, str]] = []

    def verify(self, path: Path, signature: str, manifest: dict) -> None:
        self.calls.append((str(path), signature))
        if not self.accept:
            raise OtaError("chu ky sai")
        if not signature:
            raise OtaError("thieu chu ky")


class FakeInstaller:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.installed: list[tuple[str, str]] = []
        self.rollbacks = 0

    def install(self, path: Path, version: str) -> str:
        if self.fail:
            raise OtaError("ghi slot loi")
        self.installed.append((str(path), version))
        return "B"

    def rollback(self) -> None:
        self.rollbacks += 1


def manifest_for(payload: bytes, version: str = "1.2.0", **extra) -> dict:
    data = {
        "version": version,
        "url": f"https://example.com/{version}.img",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "signature": "c2lnbmF0dXJl",
    }
    data.update(extra)
    return data


class OtaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = FakeClock(start=1_700_000_000.0)
        self.downloader = FakeDownloader()
        self.verifier = FakeVerifier()
        self.installer = FakeInstaller()
        self.manager = self._make()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make(self) -> OtaManager:
        return OtaManager(
            self.root,
            self.clock,
            self.downloader,
            self.installer,
            self.verifier,
            health_timeout_s=300.0,
        )

    def test_stage_success(self) -> None:
        status = self.manager.stage(manifest_for(self.downloader.payload))
        self.assertEqual(status.state, STATE_STAGED)
        self.assertEqual(status.version, "1.2.0")
        self.assertTrue(Path(status.image or "").exists())
        self.assertEqual(len(self.verifier.calls), 1)

    def test_stage_rejects_bad_sha(self) -> None:
        manifest = manifest_for(self.downloader.payload, sha256="0" * 64)
        with self.assertRaises(OtaError):
            self.manager.stage(manifest)
        self.assertEqual(self.manager.state, STATE_FAILED)
        self.assertFalse(list(self.root.joinpath("staging").glob("*.img")))

    def test_stage_rejects_wrong_size(self) -> None:
        manifest = manifest_for(self.downloader.payload, size=len(self.downloader.payload) + 1)
        with self.assertRaises(OtaError):
            self.manager.stage(manifest)
        self.assertEqual(self.manager.state, STATE_FAILED)

    def test_stage_rejects_short_download(self) -> None:
        manifest = manifest_for(self.downloader.payload, size=len(self.downloader.payload) + 50)
        with self.assertRaises(OtaError):
            self.manager.stage(manifest)

    def test_manifest_validation(self) -> None:
        for broken in (
            {},
            manifest_for(b"x", version="1.2"),
            manifest_for(b"x", url="ftp://x"),
            manifest_for(b"x", sha256="abc"),
            manifest_for(b"x", size=0),
            manifest_for(b"x", size="nhieu"),
        ):
            with self.assertRaises(OtaError):
                self.manager.stage(broken)
        self.assertEqual(self.downloader.calls, [])

    def test_without_verifier_refuses(self) -> None:
        manager = OtaManager(self.root, self.clock, self.downloader, self.installer, None)
        with self.assertRaises(OtaError):
            manager.stage(manifest_for(self.downloader.payload))
        self.assertEqual(manager.state, STATE_FAILED)

    def test_verifier_rejection_cleans_up(self) -> None:
        self.verifier.accept = False
        with self.assertRaises(OtaError):
            self.manager.stage(manifest_for(self.downloader.payload))
        self.assertEqual(self.manager.state, STATE_FAILED)
        self.assertFalse(list(self.root.joinpath("staging").glob("*.img")))

    def test_download_failure(self) -> None:
        self.downloader.fail = True
        with self.assertRaises(OtaError):
            self.manager.stage(manifest_for(self.downloader.payload))
        self.assertEqual(self.manager.state, STATE_FAILED)

    def test_stage_is_idempotent_for_same_version(self) -> None:
        manifest = manifest_for(self.downloader.payload)
        self.manager.stage(manifest)
        self.manager.stage(manifest)
        self.assertEqual(len(self.downloader.calls), 1)

    def test_activate_without_stage_rejected(self) -> None:
        with self.assertRaises(OtaError):
            self.manager.activate()

    def test_activate_and_health(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        status = self.manager.activate()
        self.assertEqual(status.state, STATE_ACTIVATING)
        self.assertEqual(status.slot, "B")
        self.assertEqual(len(self.installer.installed), 1)
        self.manager.mark_healthy("1.1.0")
        self.assertEqual(self.manager.state, STATE_ACTIVATING)
        status = self.manager.mark_healthy("1.2.0")
        self.assertEqual(status.state, STATE_HEALTHY)

    def test_install_failure(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        self.installer.fail = True
        with self.assertRaises(OtaError):
            self.manager.activate()
        self.assertEqual(self.manager.state, STATE_FAILED)

    def test_rollback(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        self.manager.activate()
        status = self.manager.rollback("khong khoi dong")
        self.assertEqual(status.state, STATE_ROLLED_BACK)
        self.assertEqual(self.installer.rollbacks, 1)

    def test_check_boot_overdue_rolls_back(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        self.manager.activate()
        self.clock.advance(400.0)
        status = self.manager.check_boot("1.1.0")
        self.assertEqual(status.state, STATE_ROLLED_BACK)
        self.assertEqual(self.installer.rollbacks, 1)

    def test_check_boot_healthy(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        self.manager.activate()
        self.clock.advance(10.0)
        status = self.manager.check_boot("1.2.0")
        self.assertEqual(status.state, STATE_HEALTHY)

    def test_state_survives_restart(self) -> None:
        self.manager.stage(manifest_for(self.downloader.payload))
        reopened = self._make()
        self.assertEqual(reopened.state, STATE_STAGED)
        self.assertEqual(reopened.status().version, "1.2.0")
        reopened.activate()
        self.assertEqual(reopened.state, STATE_ACTIVATING)

    def test_corrupt_state_file_raises(self) -> None:
        (self.root / "ota-state.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(OtaError):
            self._make()


if __name__ == "__main__":
    unittest.main(verbosity=2)
