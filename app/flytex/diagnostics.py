"""Chẩn đoán: log vòng và trạng thái khởi động bền.

`/data/diag/flytex.log` bị chặn kích thước: khi vượt `max_bytes`, giữ lại nửa
cuối theo ranh giới dòng. `state.json` chứa `boot_count`,
`last_shutdown_reason`, `last_battery_mv` và được ghi nguyên tử
(file tạm + `os.replace`).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .clock import Clock

__all__ = ["Diagnostics", "DiagnosticsError"]

_LEVELS = ("debug", "info", "warning", "error")


class DiagnosticsError(Exception):
    """Không đọc/ghi được dữ liệu chẩn đoán."""


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


class Diagnostics:
    """Log vòng và trạng thái khởi động."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        clock: Clock,
        max_bytes: int = 64 * 1024,
    ) -> None:
        if max_bytes < 1024:
            raise ValueError("max_bytes phai >= 1024")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "flytex.log"
        self.state_path = self.root / "state.json"
        self._clock = clock
        self._max_bytes = int(max_bytes)
        self._state: dict[str, object] = {
            "boot_count": 0,
            "last_shutdown_reason": None,
            "last_battery_mv": None,
            "last_boot_reason": None,
        }
        self.rotations = 0
        self._load_state()

    # -- trạng thái ----------------------------------------------------
    @property
    def boot_count(self) -> int:
        return _as_int(self._state.get("boot_count"))

    @property
    def last_shutdown_reason(self) -> str | None:
        value = self._state.get("last_shutdown_reason")
        return str(value) if value is not None else None

    @property
    def last_battery_mv(self) -> int | None:
        value = self._state.get("last_battery_mv")
        return _as_int(value) if value is not None else None

    @property
    def last_boot_reason(self) -> str | None:
        value = self._state.get("last_boot_reason")
        return str(value) if value is not None else None

    def state_dict(self) -> dict[str, object]:
        return dict(self._state)

    def record_boot(self, reason: str) -> int:
        """Tăng bộ đếm khởi động, lưu lý do; trả bộ đếm mới."""
        count = self.boot_count + 1
        self._state["boot_count"] = count
        self._state["last_boot_reason"] = str(reason)
        self._save_state()
        self.log("info", f"boot reason={reason} boot_count={count}")
        return count

    def record_shutdown(self, reason: str, batt_mv: int) -> None:
        self._state["last_shutdown_reason"] = str(reason)
        self._state["last_battery_mv"] = int(batt_mv)
        self._save_state()
        self.log("info", f"shutdown reason={reason} batt_mv={batt_mv}")

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.log("error", f"state.json hong, dung mac dinh: {exc}")
            return
        if not isinstance(data, dict):
            self.log("error", "state.json khong phai object, dung mac dinh")
            return
        for key in ("boot_count", "last_shutdown_reason", "last_battery_mv",
                    "last_boot_reason"):
            if key in data:
                self._state[key] = data[key]

    def _save_state(self) -> None:
        body = json.dumps(self._state, ensure_ascii=False, indent=2, sort_keys=True)
        body += "\n"
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix="state.", suffix=".tmp", dir=str(self.root)
            )
        except OSError as exc:
            raise DiagnosticsError(f"khong tao duoc file tam: {exc}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise DiagnosticsError(f"khong ghi duoc state.json: {exc}") from exc

    # -- log -----------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        """Ghi một dòng log; vượt hạn thì cắt bớt nửa đầu."""
        level_key = str(level).lower()
        if level_key not in _LEVELS:
            raise ValueError(f"log level khong hop le: {level!r}")
        text = str(message).replace("\r", " ").replace("\n", " | ")
        if len(text) > 2000:
            text = text[:1997] + "..."
        stamp = datetime.fromtimestamp(
            self._clock.now(), tz=UTC
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{stamp} {level_key.upper()} {text}\n"
        try:
            with open(self.log_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
        except OSError as exc:
            raise DiagnosticsError(f"khong ghi duoc log: {exc}") from exc
        self._trim()

    def _trim(self) -> None:
        try:
            size = self.log_path.stat().st_size
        except OSError:
            return
        if size <= self._max_bytes:
            return
        try:
            raw = self.log_path.read_bytes()
        except OSError as exc:
            raise DiagnosticsError(f"khong doc duoc log: {exc}") from exc
        keep = raw[-(self._max_bytes // 2):]
        index = keep.find(b"\n")
        if index >= 0:
            keep = keep[index + 1:]
        header = b"[rotated] older lines dropped\n"
        try:
            with open(self.log_path, "wb") as handle:
                handle.write(header)
                handle.write(keep)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise DiagnosticsError(f"khong cat duoc log: {exc}") from exc
        self.rotations += 1

    def read_log(self) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        except OSError as exc:
            raise DiagnosticsError(f"khong doc duoc log: {exc}") from exc
