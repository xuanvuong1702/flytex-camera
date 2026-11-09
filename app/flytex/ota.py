"""OTA an toàn: tải image, xác minh, cài vào slot B, quay lui khi không khỏe.

Nguyên tắc:
- Không có bộ xác minh chữ ký thì **từ chối** cập nhật, không "tạm chấp nhận".
- Mọi bước ghi trạng thái xuống đĩa trước khi hành động, để mất điện giữa chừng
  vẫn biết mình đang ở đâu.
- Cài đặt thật (ghi eMMC, đổi cờ boot, reboot) do `Installer` lo; module này
  không tự đoán thiết bị.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .clock import Clock

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

STATE_IDLE = "idle"
STATE_STAGED = "staged"
STATE_ACTIVATING = "activating"
STATE_HEALTHY = "healthy"
STATE_ROLLED_BACK = "rolled_back"
STATE_FAILED = "failed"

_ALLOWED_FROM = {
    STATE_IDLE,
    STATE_HEALTHY,
    STATE_ROLLED_BACK,
    STATE_FAILED,
}


class OtaError(Exception):
    """OTA bị từ chối hoặc thất bại."""


class Verifier(Protocol):
    def verify(self, path: Path, signature: str, manifest: dict) -> None:
        """Ném OtaError nếu chữ ký/image không hợp lệ."""


class Downloader(Protocol):
    def download(self, url: str, dest: Path, expected_size: int, timeout: float) -> int:
        """Tải `url` xuống `dest`; trả số byte. Ném OtaError nếu lỗi."""


class Installer(Protocol):
    def install(self, path: Path, version: str) -> str:
        """Ghi image vào slot còn trống, đặt cờ boot; trả tên slot."""

    def rollback(self) -> None:
        """Quay lui về slot trước."""


class NoVerifier:
    """Từ chối mọi bản cập nhật: chưa cấu hình khóa công khai."""

    def verify(self, path: Path, signature: str, manifest: dict) -> None:
        raise OtaError("chua cau hinh bo xac minh chu ky; tu choi cap nhat")


class HttpDownloader:
    """Tải qua HTTPS, ghi từng khối, không giữ cả file trong RAM."""

    def __init__(self, timeout: float = 60.0, chunk_size: int = 256 * 1024) -> None:
        self.timeout = float(timeout)
        self.chunk_size = int(chunk_size)

    def download(self, url: str, dest: Path, expected_size: int, timeout: float) -> int:
        import contextlib
        import urllib.error
        import urllib.request

        if not url.startswith("https://"):
            raise OtaError(f"chi chap nhan HTTPS: {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with urllib.request.urlopen(  # nosec B310
                url, timeout=timeout or self.timeout
            ) as response:
                if not response.geturl().startswith("https://"):
                    raise OtaError("redirect ra khoi HTTPS")
                with dest.open("wb") as handle:
                    while True:
                        chunk = response.read(self.chunk_size)
                        if not chunk:
                            break
                        handle.write(chunk)
                        written += len(chunk)
                        if expected_size and written > expected_size:
                            raise OtaError("image lon hon khai bao")
                    handle.flush()
                    os.fsync(handle.fileno())
        except urllib.error.HTTPError as exc:
            with contextlib.suppress(OSError):
                exc.close()
            raise OtaError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OtaError(f"loi tai image: {exc}") from exc
        return written


@dataclass
class OtaStatus:
    state: str
    version: str | None
    image: str | None
    slot: str | None
    last_error: str | None


class OtaManager:
    """Máy trạng thái OTA; một thiết bị một manager."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        clock: Clock,
        downloader: Downloader,
        installer: Installer,
        verifier: Verifier | None = None,
        *,
        download_timeout: float = 120.0,
        health_timeout_s: float = 300.0,
    ) -> None:
        if download_timeout <= 0 or health_timeout_s <= 0:
            raise ValueError("timeout phai > 0")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging = self.root / "staging"
        self.staging.mkdir(exist_ok=True)
        self.state_path = self.root / "ota-state.json"
        self.clock = clock
        self.downloader = downloader
        self.installer = installer
        self.verifier = verifier if verifier is not None else NoVerifier()
        self.download_timeout = float(download_timeout)
        self.health_timeout_s = float(health_timeout_s)
        self._state: dict = {
            "state": STATE_IDLE,
            "version": None,
            "image": None,
            "slot": None,
            "signature": None,
            "activated_at": None,
            "last_error": None,
        }
        self._load()

    # -- trạng thái -----------------------------------------------------
    @property
    def state(self) -> str:
        return str(self._state["state"])

    def status(self) -> OtaStatus:
        return OtaStatus(
            state=self.state,
            version=self._state.get("version"),
            image=self._state.get("image"),
            slot=self._state.get("slot"),
            last_error=self._state.get("last_error"),
        )

    # -- API ------------------------------------------------------------
    def stage(self, manifest: dict) -> OtaStatus:
        """Tải và xác minh image; chưa cài. Idempotent theo version."""
        version, url, sha256, size = self._validate(manifest)
        if self.state == STATE_STAGED:
            if self._state.get("version") == version:
                return self.status()
            raise OtaError(
                f"dang co image staged {self._state.get('version')}; "
                f"khong stage {version} khi chua activate"
            )
        if self.state not in _ALLOWED_FROM:
            raise OtaError(f"khong the stage khi dang {self.state}")
        image = self.staging / f"{version}.img"
        try:
            written = self.downloader.download(
                url, image, size, self.download_timeout
            )
            if size and written != size:
                raise OtaError(f"kich thuoc sai: {written} != {size}")
            digest = self._sha256(image)
            if digest != sha256:
                raise OtaError(f"sha256 sai: {digest}")
            self.verifier.verify(image, str(manifest.get("signature", "")), manifest)
        except Exception as exc:
            image.unlink(missing_ok=True)
            self._fail(str(exc))
            if isinstance(exc, OtaError):
                raise
            raise OtaError(f"stage that bai: {exc}") from exc
        self._state.update(
            {
                "state": STATE_STAGED,
                "version": version,
                "image": str(image),
                "slot": None,
                "signature": str(manifest.get("signature", "")),
                "last_error": None,
            }
        )
        self._save()
        return self.status()

    def activate(self) -> OtaStatus:
        """Ghi image vào slot B và đặt cờ boot; cần khởi động lại để áp dụng."""
        if self.state != STATE_STAGED:
            raise OtaError(f"chua co image staged (dang {self.state})")
        image = Path(str(self._state["image"]))
        if not image.exists():
            self._fail("image staged khong con")
            raise OtaError("image staged khong con")
        try:
            slot = self.installer.install(image, str(self._state["version"]))
        except Exception as exc:
            self._fail(f"install that bai: {exc}")
            raise OtaError(f"install that bai: {exc}") from exc
        self._state.update(
            {"state": STATE_ACTIVATING, "slot": slot,
             "activated_at": self.clock.now(), "last_error": None}
        )
        self._save()
        return self.status()

    def mark_healthy(self, running_version: str) -> OtaStatus:
        """Sau khi khởi động lại và chạy ổn: chốt image mới."""
        if self.state != STATE_ACTIVATING:
            return self.status()
        if running_version != self._state.get("version"):
            return self.status()
        self._state.update({"state": STATE_HEALTHY, "slot": self._state.get("slot")})
        self._save()
        return self.status()

    def check_boot(self, running_version: str) -> OtaStatus:
        """Gọi sớm sau khởi động: quá hạn không khỏe thì quay lui."""
        if self.state != STATE_ACTIVATING:
            return self.status()
        activated_at = self._state.get("activated_at")
        overdue = (
            isinstance(activated_at, (int, float))
            and self.clock.now() - float(activated_at) > self.health_timeout_s
        )
        if running_version == self._state.get("version") and not overdue:
            return self.mark_healthy(running_version)
        self.rollback("khong khoi dong duoc hoac qua han")
        return self.status()

    def rollback(self, reason: str = "") -> OtaStatus:
        if self.state != STATE_ACTIVATING:
            raise OtaError(f"khong co gi de quay lui (dang {self.state})")
        try:
            self.installer.rollback()
        except Exception as exc:
            self._fail(f"rollback that bai: {exc}")
            raise OtaError(f"rollback that bai: {exc}") from exc
        self._state.update(
            {"state": STATE_ROLLED_BACK, "slot": None, "image": None,
             "last_error": reason or None}
        )
        self._save()
        return self.status()

    # -- nội bộ ---------------------------------------------------------
    @staticmethod
    def _validate(manifest: dict) -> tuple[str, str, str, int]:
        if not isinstance(manifest, dict):
            raise OtaError("manifest phai la object")
        version = str(manifest.get("version", ""))
        url = str(manifest.get("url", ""))
        sha256 = str(manifest.get("sha256", "")).lower()
        try:
            size = int(manifest.get("size", 0))
        except (TypeError, ValueError) as exc:
            raise OtaError("size phai la so") from exc
        if not VERSION_RE.match(version):
            raise OtaError(f"version khong hop le: {version!r}")
        if not url.startswith(("http://", "https://")):
            raise OtaError(f"url khong hop le: {url!r}")
        if not SHA256_RE.match(sha256):
            raise OtaError("sha256 phai la 64 hex thuong")
        if size <= 0:
            raise OtaError("size phai > 0")
        return version, url, sha256, size

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _fail(self, message: str) -> None:
        self._state.update({"state": STATE_FAILED, "last_error": message[:300]})
        self._save()

    def _save(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OtaError(f"trang thai OTA hong: {exc}") from exc
        if isinstance(data, dict):
            for key in self._state:
                if key in data:
                    self._state[key] = data[key]
