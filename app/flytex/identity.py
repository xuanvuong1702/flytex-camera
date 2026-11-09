"""Định danh thiết bị và chứng chỉ TLS.

`/data/identity/` chứa `device_id`, `cert.pem`, `key.pem`, `ca.pem` (docs/14
§5). Thiếu file nào thì báo đúng file đó, không rơi về giá trị mặc định.

`generate_for_test` chỉ dùng cho test/sim: nội dung PEM là fixture, **không
phải chứng chỉ thật** và TLS sẽ từ chối.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Identity", "IdentityError"]

_DEVICE_ID_RE = re.compile(r"^[a-z0-9]{12}$")
_REQUIRED_FILES = ("cert.pem", "key.pem", "ca.pem")


class IdentityError(Exception):
    """Thiếu hoặc sai định danh thiết bị."""


@dataclass(frozen=True)
class Identity:
    """Định danh đã kiểm tra."""

    device_id: str
    root: str
    cert_path: str
    key_path: str
    ca_path: str

    @property
    def cert_paths(self) -> tuple[str, str, str]:
        """(cert, key, ca) để cấu hình TLS."""
        return (self.cert_path, self.key_path, self.ca_path)

    @classmethod
    def load(cls, root: str | os.PathLike[str]) -> Identity:
        directory = Path(root)
        if not directory.is_dir():
            raise IdentityError(f"khong thay thu muc dinh danh: {directory}")
        device_file = directory / "device_id"
        try:
            raw = device_file.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise IdentityError(f"thieu file device_id trong {directory}") from exc
        except OSError as exc:
            raise IdentityError(f"khong doc duoc device_id: {exc}") from exc
        device_id = raw.strip()
        if not _DEVICE_ID_RE.match(device_id):
            raise IdentityError(
                "device_id phai gom dung 12 ky tu [a-z0-9]: "
                f"{device_id!r}"
            )
        missing: list[str] = []
        for name in _REQUIRED_FILES:
            path = directory / name
            if not path.is_file():
                missing.append(name)
                continue
            try:
                if path.stat().st_size == 0:
                    missing.append(name)
            except OSError:
                missing.append(name)
        if missing:
            raise IdentityError(
                "thieu hoac rong file dinh danh: " + ", ".join(missing)
            )
        return cls(
            device_id=device_id,
            root=str(directory),
            cert_path=str(directory / "cert.pem"),
            key_path=str(directory / "key.pem"),
            ca_path=str(directory / "ca.pem"),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "device_id": self.device_id,
            "root": self.root,
            "cert": self.cert_path,
            "key": self.key_path,
            "ca": self.ca_path,
        }

    @classmethod
    def generate_for_test(cls, root: str | os.PathLike[str]) -> Identity:
        """Tạo bộ định danh giả cho test/sim (không dùng cho sản phẩm)."""
        return generate_identity_for_test(root)


def _fake_pem(label: str) -> str:
    marker = f"FLYTEX TEST FIXTURE ONLY - NOT A REAL {label} - DO NOT USE IN PRODUCTION"
    body = base64.b64encode(marker.encode("ascii")).decode("ascii")
    return (
        f"# FLYTEX TEST FIXTURE - NOT A REAL {label}\n"
        f"-----BEGIN {label}-----\n"
        f"{body}\n"
        f"-----END {label}-----\n"
    )


def _write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        return
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def generate_identity_for_test(root: str | os.PathLike[str]) -> Identity:
    """Tạo bộ định danh giả cho test/sim (không dùng cho sản phẩm)."""
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    device_file = directory / "device_id"
    if not device_file.exists():
        _write_if_missing(device_file, secrets.token_hex(6) + "\n")
    _write_if_missing(directory / "cert.pem", _fake_pem("CERTIFICATE"))
    _write_if_missing(directory / "key.pem", _fake_pem("PRIVATE KEY"))
    _write_if_missing(directory / "ca.pem", _fake_pem("CERTIFICATE"))
    return Identity.load(directory)


# Tên ngắn dùng trong test/sim, vẫn nói rõ mục đích.
generate_for_test = generate_identity_for_test
