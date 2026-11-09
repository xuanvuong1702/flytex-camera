"""Tiện ích dùng chung cho test ứng dụng."""

from __future__ import annotations

try:  # chạy trực tiếp: python app/tests/test_x.py
    from _bootstrap import APP, ROOT
except ImportError:  # chạy bằng discover: app.tests.test_x
    from app.tests._bootstrap import APP, ROOT  # noqa: F401

from flytex.clock import FakeClock
from flytex.mcu import McuClient, MemoryMcu
from flytex.recorder import ClipInfo


def make_mcu(clock: FakeClock | None = None, proto_ver: int | None = None):
    """Trả (McuClient, MemoryMcu, clock) cho test không cần phần cứng."""
    clock = clock if clock is not None else FakeClock()
    memory = MemoryMcu(clock) if proto_ver is None else MemoryMcu(clock, proto_ver=proto_ver)
    return McuClient(memory), memory, clock


class FakeRecorder:
    """Ghi giả: ghi lại clip_id và số frame, không chạm đĩa."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.recording = False
        self.clip_id: str | None = None
        self.ir = False
        self.started: list[str] = []
        self.frames = 0
        self.fail_on_stop: Exception | None = None

    def start(self, clip_id: str, ir: bool = False) -> None:
        if self.recording:
            raise RuntimeError("recorder dang ghi")
        self.recording = True
        self.clip_id = clip_id
        self.ir = ir
        self.started.append(clip_id)

    def write(self, pts: float, data: bytes) -> None:
        if not self.recording:
            raise RuntimeError("recorder chua bat dau")
        self.frames += 1

    def stop(self) -> ClipInfo:
        if not self.recording:
            raise RuntimeError("recorder khong ghi")
        if self.fail_on_stop is not None:
            raise self.fail_on_stop
        self.recording = False
        clip_id = self.clip_id or "0" * 16
        return ClipInfo(
            clip_id=clip_id,
            path=f"/tmp/{clip_id}",
            segments=(f"/tmp/{clip_id}.part",),
            size_b=1024,
            duration_s=1.5,
            started_ts=0.0,
            ir=self.ir,
            pinned=False,
        )


class FakeUplink:
    """Hàng đợi giả: ghi lại bản tin và độ ưu tiên."""

    def __init__(self) -> None:
        self.items: list[tuple[str, dict]] = []

    def enqueue(self, msg: dict, priority: str = "normal") -> str:
        self.items.append((priority, dict(msg)))
        return f"{len(self.items):016x}"

    def types(self) -> list[str]:
        return [str(msg.get("type")) for _, msg in self.items]
