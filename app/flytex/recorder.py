"""Ghi clip thành đoạn lên thẻ nhớ, chịu được mất điện.

Mỗi clip là một thư mục trong `root`, gồm nhiều đoạn có giới hạn thời gian và
kích thước. Đoạn đang ghi có đuôi `.part`; khi đóng: `flush`, `os.fsync`,
`end()`, rồi `os.rename` sang tên cuối. Chỉ mục là `index.jsonl` append-only,
có `fsync` sau mỗi dòng.

`RawMuxer` chỉ để bring-up: định dạng có độ dài tiền tố, **không phải
container phát được**. Khi `allow_raw_muxer=False` nó bị từ chối.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .clock import Clock

__all__ = [
    "ClipInfo",
    "Muxer",
    "RawMuxer",
    "RecorderError",
    "RecoveryReport",
    "SegmentRecorder",
]

_CLIP_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_RAW_MAGIC = b"FLTXRAW1\n"


class RecorderError(Exception):
    """Lỗi ghi clip, chỉ mục hoặc muxer."""


@dataclass(frozen=True)
class ClipInfo:
    """Thông tin một clip đã đóng (hoặc đang có trong chỉ mục)."""

    clip_id: str
    path: str
    segments: tuple[str, ...]
    size_b: int
    duration_s: float
    started_ts: float
    ir: bool
    pinned: bool


@dataclass(frozen=True)
class RecoveryReport:
    """Kết quả dọn dẹp sau mất điện."""

    removed_parts: tuple[str, ...]
    dropped_index_lines: int
    index_repaired: bool
    clips: int


@dataclass
class _ClipState:
    clip_id: str
    path: Path
    started_ts: float = 0.0
    ir: bool = False
    pinned: bool = False
    segments: list[str] = field(default_factory=list)
    size_b: int = 0
    duration_s: float = 0.0

    def info(self) -> ClipInfo:
        return ClipInfo(
            clip_id=self.clip_id,
            path=str(self.path),
            segments=tuple(self.segments),
            size_b=self.size_b,
            duration_s=self.duration_s,
            started_ts=self.started_ts,
            ir=self.ir,
            pinned=self.pinned,
        )


@dataclass
class _ActiveSegment:
    clip_id: str
    index: int
    part_path: Path
    started_mono: float
    started_ts: float
    ir: bool
    bytes_written: int = 0


class Muxer:
    """Hợp đồng đóng gói đoạn.

    `begin(path)` mở đoạn mới, `write(pts, data)` ghi một frame, `end()` đóng
    và trả số byte của đoạn. Hiện thực nên có thêm `flush()` để recorder gọi
    `os.fsync` trước khi đóng.
    """

    def begin(self, path: str) -> None:
        raise NotImplementedError

    def write(self, pts: float, data: bytes) -> None:
        raise NotImplementedError

    def end(self) -> int:
        raise NotImplementedError


class RawMuxer(Muxer):
    """Ghi frame có độ dài tiền tố, **chỉ để bring-up**.

    Định dạng: magic ``FLTXRAW1\\n``, sau đó từng bản ghi
    ``<double pts little-endian><uint32 len little-endian><data>``.
    Đây không phải MP4/TS và không phát được bằng trình phát thông thường;
    chỉ dùng để kiểm tra đường ống ghi và độ bền khi mất điện.
    """

    extension = "raw"

    def __init__(self) -> None:
        self._file: object | None = None
        self._bytes = 0
        self._path: str | None = None

    def begin(self, path: str) -> None:
        if self._file is not None:
            raise RecorderError("RawMuxer dang mo mot doan khac")
        handle = open(path, "wb")
        handle.write(_RAW_MAGIC)
        self._file = handle
        self._bytes = len(_RAW_MAGIC)
        self._path = path

    def write(self, pts: float, data: bytes) -> None:
        if self._file is None:
            raise RecorderError("RawMuxer chua begin")
        payload = bytes(data)
        if len(payload) > 0xFFFF_FFFF:
            raise RecorderError("frame qua lon cho dinh dang raw")
        header = struct.pack("<dI", float(pts), len(payload))
        self._file.write(header)  # type: ignore[attr-defined]
        self._file.write(payload)  # type: ignore[attr-defined]
        self._bytes += len(header) + len(payload)

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()  # type: ignore[attr-defined]

    def end(self) -> int:
        if self._file is None:
            raise RecorderError("RawMuxer chua begin")
        handle = self._file
        self._file = None
        handle.flush()  # type: ignore[attr-defined]
        handle.close()  # type: ignore[attr-defined]
        size = self._bytes
        self._path = None
        return size


class SegmentRecorder:
    """Ghi clip thành nhiều đoạn, quản lý vòng ghi và clip được ghim."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        clock: Clock,
        muxer: Muxer,
        segment_s: float = 20.0,
        max_bytes: int = 512 * 1024 * 1024,
        pin_budget_bytes: int = 256 * 1024 * 1024,
        segment_max_bytes: int = 8 * 1024 * 1024,
        allow_raw_muxer: bool = True,
    ) -> None:
        if segment_s <= 0:
            raise ValueError("segment_s phai > 0")
        if max_bytes <= 0:
            raise ValueError("max_bytes phai > 0")
        if pin_budget_bytes < 0:
            raise ValueError("pin_budget_bytes phai >= 0")
        if segment_max_bytes <= 0:
            raise ValueError("segment_max_bytes phai > 0")
        if isinstance(muxer, RawMuxer) and not allow_raw_muxer:
            raise RecorderError(
                "RawMuxer bi tu choi vi config.allow_raw_muxer=False; "
                "can muxer container that (MP4/TS)"
            )
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._muxer = muxer
        self._segment_s = float(segment_s)
        self._max_bytes = int(max_bytes)
        self._pin_budget_bytes = int(pin_budget_bytes)
        self._segment_max_bytes = int(segment_max_bytes)
        self._index_path = self.root / "index.jsonl"
        self._clips: dict[str, _ClipState] = {}
        self._active: _ActiveSegment | None = None
        self._next_segment = 0
        self.corrupt_index_lines = 0
        self._load_index()

    # -- thuộc tính ----------------------------------------------------
    @property
    def muxer(self) -> Muxer:
        return self._muxer

    @property
    def index_path(self) -> Path:
        return self._index_path

    @property
    def recording(self) -> bool:
        return self._active is not None

    # -- ghi -----------------------------------------------------------
    def start(self, clip_id: str, ir: bool = False) -> None:
        """Bắt đầu một clip mới với `clip_id` 16 hex."""
        if self._active is not None:
            raise RecorderError(
                f"dang ghi clip {self._active.clip_id}, khong the start clip khac"
            )
        if not _CLIP_ID_RE.match(clip_id):
            raise RecorderError("clip_id phai la 16 ky tu hex thuong")
        if clip_id in self._clips:
            raise RecorderError(f"clip_id da ton tai trong chi muc: {clip_id}")
        clip_dir = self.root / clip_id
        try:
            clip_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            try:
                empty = not any(clip_dir.iterdir())
            except OSError:
                empty = False
            if not empty:
                raise RecorderError(
                    f"thu muc clip da ton tai va con du lieu: {clip_id}; "
                    "hay chay recover() truoc"
                ) from None
        self._next_segment = 0
        self._open_segment(clip_id, clip_dir, ir=bool(ir))

    def write(self, pts: float, data: bytes) -> None:
        if self._active is None:
            raise RecorderError("chua start clip")
        payload = bytes(data)
        if not payload:
            raise RecorderError("frame rong")
        self._muxer.write(float(pts), payload)
        self._active.bytes_written += len(payload)
        duration = self._clock.monotonic() - self._active.started_mono
        if (
            self._active.bytes_written >= self._segment_max_bytes
            or duration >= self._segment_s
        ):
            self._rotate()

    def stop(self) -> ClipInfo:
        """Đóng đoạn cuối, ghi chỉ mục và trả thông tin clip."""
        active = self._active
        if active is None:
            raise RecorderError("khong co clip nao dang ghi")
        self._close_segment()
        self._active = None
        state = self._clips.get(active.clip_id)
        if state is None:  # pragma: no cover - _close_segment luôn tạo state
            raise RecorderError("mat trang thai clip sau khi dong")
        return state.info()

    def _open_segment(self, clip_id: str, clip_dir: Path, ir: bool) -> None:
        extension = str(getattr(self._muxer, "extension", "bin"))
        name = f"seg-{self._next_segment:05d}.{extension}"
        part_path = clip_dir / (name + ".part")
        self._muxer.begin(str(part_path))
        self._active = _ActiveSegment(
            clip_id=clip_id,
            index=self._next_segment,
            part_path=part_path,
            started_mono=self._clock.monotonic(),
            started_ts=self._clock.now(),
            ir=ir,
        )
        self._next_segment += 1

    def _rotate(self) -> None:
        active = self._active
        if active is None:
            return
        self._close_segment()
        clip_dir = self.root / active.clip_id
        self._open_segment(active.clip_id, clip_dir, active.ir)

    def _close_segment(self) -> tuple[Path, int, float] | None:
        active = self._active
        if active is None:
            return None
        part_path = active.part_path
        flush = getattr(self._muxer, "flush", None)
        if callable(flush):
            flush()
        self._fsync_path(part_path)
        size = int(self._muxer.end())
        duration = max(0.0, self._clock.monotonic() - active.started_mono)
        final_path = part_path.with_name(part_path.name[:-5])
        os.replace(part_path, final_path)
        record = {
            "kind": "segment",
            "clip_id": active.clip_id,
            "name": final_path.name,
            "size_b": size,
            "duration_s": round(duration, 6),
            "started_ts": active.started_ts,
            "ir": active.ir,
        }
        self._append_index(record)
        state = self._clips.get(active.clip_id)
        if state is None:
            state = _ClipState(
                clip_id=active.clip_id,
                path=self.root / active.clip_id,
                started_ts=active.started_ts,
                ir=active.ir,
            )
            self._clips[active.clip_id] = state
        if not state.segments:
            state.started_ts = active.started_ts
            state.ir = active.ir
        state.segments.append(final_path.name)
        state.size_b += size
        state.duration_s += duration
        return final_path, size, duration

    # -- chỉ mục và quản lý clip --------------------------------------
    def list_clips(self) -> list[ClipInfo]:
        items = sorted(
            self._clips.values(), key=lambda clip: (clip.started_ts, clip.clip_id)
        )
        return [clip.info() for clip in items]

    def clip(self, clip_id: str) -> ClipInfo | None:
        state = self._clips.get(clip_id)
        return state.info() if state is not None else None

    def pin(self, clip_id: str) -> ClipInfo:
        """Ghim clip để vòng ghi không xóa; vẫn có trần `pin_budget_bytes`."""
        state = self._clips.get(clip_id)
        if state is None:
            raise RecorderError(f"khong co clip de pin: {clip_id}")
        if not state.pinned:
            self._append_index({"kind": "pin", "clip_id": clip_id})
            state.pinned = True
        return state.info()

    def unpin(self, clip_id: str) -> ClipInfo:
        state = self._clips.get(clip_id)
        if state is None:
            raise RecorderError(f"khong co clip de unpin: {clip_id}")
        if state.pinned:
            self._append_index({"kind": "unpin", "clip_id": clip_id})
            state.pinned = False
        return state.info()

    def evict(self) -> list[str]:
        """Xóa clip cũ theo vòng; trả danh sách id đã xóa theo thứ tự.

        Clip ghim không bị xóa vì ngân sách chung, nhưng tổng dung lượng clip
        ghim bị chặn bởi `pin_budget_bytes`; vượt trần thì clip ghim cũ nhất
        bị xóa (đây là "có trần" trong docs/14 §4.3).
        """
        evicted: list[str] = []
        while self._pinned_bytes() > self._pin_budget_bytes:
            victim = self._oldest(pinned=True)
            if victim is None:
                break
            self._drop_clip(victim, reason="pin_budget")
            evicted.append(victim)
        while self._total_bytes() > self._max_bytes:
            victim = self._oldest(pinned=False) or self._oldest(pinned=True)
            if victim is None:
                break
            self._drop_clip(victim, reason="capacity")
            evicted.append(victim)
        return evicted

    def free_mb(self) -> int:
        usage = shutil.disk_usage(self.root)
        return int(usage.free // (1024 * 1024))

    def total_bytes(self) -> int:
        return self._total_bytes()

    # -- phục hồi sau mất điện ----------------------------------------
    def recover(self) -> RecoveryReport:
        """Xóa `.part` mồ côi và sửa chỉ mục bị cắt giữa dòng."""
        removed: list[str] = []
        for part in sorted(self.root.rglob("*.part")):
            try:
                part.unlink()
            except OSError as exc:
                raise RecorderError(f"khong xoa duoc {part}: {exc}") from exc
            removed.append(str(part.relative_to(self.root)))
        for directory in sorted(self.root.iterdir()):
            if directory.is_dir():
                try:
                    if not any(directory.iterdir()):
                        directory.rmdir()
                except OSError as exc:
                    raise RecorderError(
                        f"khong don duoc thu muc {directory}: {exc}"
                    ) from exc
        dropped, repaired = self._repair_index()
        self._load_index()
        return RecoveryReport(
            removed_parts=tuple(removed),
            dropped_index_lines=dropped,
            index_repaired=repaired,
            clips=len(self._clips),
        )

    # -- nội bộ --------------------------------------------------------
    def _pinned_bytes(self) -> int:
        return sum(clip.size_b for clip in self._clips.values() if clip.pinned)

    def _total_bytes(self) -> int:
        return sum(clip.size_b for clip in self._clips.values())

    def _oldest(self, pinned: bool) -> str | None:
        candidates = [
            clip for clip in self._clips.values() if clip.pinned is pinned
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda clip: (clip.started_ts, clip.clip_id)).clip_id

    def _drop_clip(self, clip_id: str, reason: str) -> None:
        state = self._clips.pop(clip_id, None)
        if state is None:
            return
        try:
            shutil.rmtree(state.path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RecorderError(f"khong xoa duoc clip {clip_id}: {exc}") from exc
        self._append_index({"kind": "drop", "clip_id": clip_id, "reason": reason})

    def _fsync_path(self, path: Path) -> None:
        try:
            fd = os.open(str(path), os.O_RDWR)
        except OSError as exc:
            raise RecorderError(f"khong mo duoc {path} de fsync: {exc}") from exc
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _append_index(self, record: dict[str, object]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        try:
            with open(self._index_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise RecorderError(f"khong ghi duoc chi muc: {exc}") from exc

    def _load_index(self) -> None:
        self._clips = {}
        self.corrupt_index_lines = 0
        if not self._index_path.exists():
            return
        with open(self._index_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.corrupt_index_lines += 1
                    continue
                if not isinstance(record, dict):
                    self.corrupt_index_lines += 1
                    continue
                self._apply_record(record)

    def _apply_record(self, record: dict[str, object]) -> None:
        kind = record.get("kind")
        clip_id = record.get("clip_id")
        if not isinstance(clip_id, str):
            self.corrupt_index_lines += 1
            return
        if kind == "segment":
            state = self._clips.get(clip_id)
            if state is None:
                state = _ClipState(clip_id=clip_id, path=self.root / clip_id)
                self._clips[clip_id] = state
            name = record.get("name")
            if isinstance(name, str) and name not in state.segments:
                state.segments.append(name)
            try:
                state.size_b += int(record.get("size_b", 0))
                state.duration_s += float(record.get("duration_s", 0.0))
                state.started_ts = float(record.get("started_ts", state.started_ts))
            except (TypeError, ValueError):
                self.corrupt_index_lines += 1
            state.ir = bool(record.get("ir", state.ir))
        elif kind == "pin":
            state = self._clips.get(clip_id)
            if state is not None:
                state.pinned = True
        elif kind == "unpin":
            state = self._clips.get(clip_id)
            if state is not None:
                state.pinned = False
        elif kind == "drop":
            self._clips.pop(clip_id, None)
        # kind lạ: bỏ qua để tiến hóa lược đồ về sau.

    def _repair_index(self) -> tuple[int, bool]:
        if not self._index_path.exists():
            return 0, False
        try:
            raw = self._index_path.read_bytes()
        except OSError as exc:
            raise RecorderError(f"khong doc duoc chi muc: {exc}") from exc
        if not raw:
            return 0, False
        chunks = raw.split(b"\n")
        tail = b""
        if not raw.endswith(b"\n"):
            tail = chunks.pop()
        valid: list[bytes] = []
        dropped = 0
        for chunk in chunks:
            if not chunk.strip():
                dropped += 1
                continue
            try:
                record = json.loads(chunk.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                dropped += 1
                break
            if not isinstance(record, dict):
                dropped += 1
                break
            valid.append(chunk)
        if tail:
            dropped += 1
        if not dropped:
            return 0, False
        body = b"\n".join(valid)
        if body:
            body += b"\n"
        temp_path = self._index_path.with_name(self._index_path.name + ".tmp")
        with open(temp_path, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, self._index_path)
        return dropped, True
