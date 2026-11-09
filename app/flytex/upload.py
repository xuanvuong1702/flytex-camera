"""Tải clip lên kho đối tượng qua HTTPS, có hàng đợi bền.

Cloud cấp URL presigned cho từng clip; thiết bị PUT file lên đó. Không dùng
multipart để giảm bộ nhớ: file được đọc một lần và gửi thẳng.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .clock import Clock


class UploadError(Exception):
    """Tải clip thất bại; có thể thử lại."""


@dataclass(frozen=True)
class UploadResult:
    clip_id: str
    url: str
    size_b: int


class Uploader(Protocol):
    def upload(self, path: str | os.PathLike[str], clip_id: str) -> UploadResult:
        ...


class HttpUploader:
    """PUT file lên URL presigned. Không giữ file trong bộ nhớ lâu hơn cần thiết."""

    def __init__(
        self,
        url_template: str,
        *,
        timeout: float = 30.0,
        content_type: str = "video/mp2t",
        clock: Clock | None = None,
    ) -> None:
        if "{clip_id}" not in url_template:
            raise ValueError("url_template phai chua {clip_id}")
        if timeout <= 0:
            raise ValueError("timeout phai > 0")
        self.url_template = url_template
        self.timeout = float(timeout)
        self.content_type = content_type
        self._clock = clock

    def upload(self, path: str | os.PathLike[str], clip_id: str) -> UploadResult:
        source = Path(path)
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise UploadError(f"khong doc duoc clip {source}: {exc}") from exc
        url = self.url_template.format(clip_id=clip_id)
        request = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={
                "Content-Type": self.content_type,
                "Content-Length": str(len(data)),
                "X-Clip-Id": clip_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 0)
                if not 200 <= int(status) < 300:
                    raise UploadError(f"may chu tra {status}")
        except urllib.error.HTTPError as exc:
            try:
                exc.close()
            except Exception:  # noqa: BLE001 - đóng lỗi không được che lỗi gốc
                pass
            raise UploadError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UploadError(f"loi mang: {exc}") from exc
        return UploadResult(clip_id=clip_id, url=url, size_b=len(data))


class FakeUploader:
    """Uploader cho test: ghi lại lần gọi, có thể cài lỗi N lần."""

    def __init__(self, fail_times: int = 0) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_times = fail_times

    def upload(self, path: str | os.PathLike[str], clip_id: str) -> UploadResult:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise UploadError("loi gia lap")
        self.calls.append((clip_id, str(path)))
        return UploadResult(clip_id=clip_id, url=f"https://fake/{clip_id}.ts",
                            size_b=Path(path).stat().st_size)


@dataclass
class UploadItem:
    clip_id: str
    path: str
    size_b: int
    attempts: int
    next_at: float


class UploadSpool:
    """Hàng đợi clip chờ tải, lưu xuống đĩa để sống qua restart."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        clock: Clock,
        *,
        max_items: int = 200,
        base_delay_s: float = 30.0,
        max_delay_s: float = 3600.0,
        max_attempts: int = 8,
    ) -> None:
        if max_items < 1 or base_delay_s <= 0 or max_delay_s < base_delay_s or max_attempts < 1:
            raise ValueError("tham so hang doi khong hop le")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self.max_items = int(max_items)
        self.base_delay_s = float(base_delay_s)
        self.max_delay_s = float(max_delay_s)
        self.max_attempts = int(max_attempts)
        self._items: dict[str, UploadItem] = {}
        self._order: list[str] = []
        self._done: set[str] = set()
        self.corrupt_lines = 0
        self._load()

    # -- API ------------------------------------------------------------
    def add(self, clip_id: str, path: str, size_b: int) -> bool:
        """Thêm clip chờ tải; trả False nếu đã có hoặc đã tải."""
        if clip_id in self._items or clip_id in self._done:
            return False
        if len(self._items) >= self.max_items:
            raise UploadError(f"hang doi day ({self.max_items} clip)")
        item = UploadItem(clip_id, path, int(size_b), 0, 0.0)
        self._items[clip_id] = item
        self._order.append(clip_id)
        self._append({"op": "add", "clip_id": clip_id, "path": path, "size_b": int(size_b)})
        return True

    def pending(self, now: float | None = None) -> UploadItem | None:
        moment = self._clock.now() if now is None else float(now)
        for clip_id in self._order:
            item = self._items.get(clip_id)
            if item is None or item.next_at > moment:
                continue
            return item
        return None

    def done(self, clip_id: str) -> bool:
        if clip_id not in self._items:
            return False
        del self._items[clip_id]
        self._order = [item for item in self._order if item != clip_id]
        self._done.add(clip_id)
        self._append({"op": "done", "clip_id": clip_id})
        return True

    def fail(self, clip_id: str, error: object = "") -> float | None:
        item = self._items.get(clip_id)
        if item is None:
            return None
        item.attempts += 1
        if item.attempts >= self.max_attempts:
            del self._items[clip_id]
            self._order = [value for value in self._order if value != clip_id]
            self._append({"op": "drop", "clip_id": clip_id, "error": str(error)[:200]})
            return None
        delay = min(self.base_delay_s * (2 ** (item.attempts - 1)), self.max_delay_s)
        item.next_at = self._clock.now() + delay
        self._append(
            {"op": "retry", "clip_id": clip_id, "attempts": item.attempts,
             "next": item.next_at, "error": str(error)[:200]}
        )
        return delay

    def stats(self) -> dict[str, object]:
        now = self._clock.now()
        due = sum(1 for item in self._items.values() if item.next_at <= now)
        return {
            "pending": len(self._items),
            "due": due,
            "done": len(self._done),
            "corrupt_lines": self.corrupt_lines,
        }

    def pending_ids(self) -> list[str]:
        return [item for item in self._order if item in self._items]

    def __len__(self) -> int:
        return len(self._items)

    # -- nội bộ ---------------------------------------------------------
    def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        try:
            with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise UploadError(f"khong ghi duoc hang doi clip: {exc}") from exc

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise UploadError(f"khong doc duoc hang doi clip: {exc}") from exc
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                self.corrupt_lines += 1
                continue
            op = record.get("op")
            clip_id = record.get("clip_id")
            if not isinstance(clip_id, str):
                self.corrupt_lines += 1
                continue
            if op == "add":
                if clip_id in self._done:
                    continue
                self._items[clip_id] = UploadItem(
                    clip_id, str(record.get("path", "")),
                    int(record.get("size_b", 0)), 0, 0.0,
                )
                if clip_id not in self._order:
                    self._order.append(clip_id)
            elif op == "done":
                self._items.pop(clip_id, None)
                self._done.add(clip_id)
                self._order = [value for value in self._order if value != clip_id]
            elif op == "retry":
                item = self._items.get(clip_id)
                if item is not None:
                    item.attempts = int(record.get("attempts", item.attempts))
                    item.next_at = float(record.get("next", item.next_at))
            elif op == "drop":
                self._items.pop(clip_id, None)
                self._order = [value for value in self._order if value != clip_id]
