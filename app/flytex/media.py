"""Nguồn hình cho ứng dụng.

Trong repo chỉ có `FakeSource` (sinh frame giả theo `Clock`) và `RkMpiSource`
trả `NotImplementedError`. **Chưa có mã chạy camera thật**: cần SDK RK MPI của
Rockchip, xem docs/14 §4.3 và bảng "Việc chưa làm".
"""

from __future__ import annotations

from typing import Protocol

from .clock import Clock


class MediaError(Exception):
    """Lỗi nguồn hình."""


class MediaSource(Protocol):
    """Nguồn frame đã mã hóa (hoặc frame thô để bring-up)."""

    def start(self) -> None:
        """Bắt đầu lấy hình."""

    def read_frame(self, timeout: float) -> tuple[float, bytes] | None:
        """Trả `(pts, data)` hoặc `None` nếu chưa có frame trong `timeout`."""

    def stop(self) -> None:
        """Dừng lấy hình."""


class FakeSource:
    """Sinh frame giả theo đồng hồ, dùng cho test và sim.

    Frame thứ `n` có pts = `t0 + n / fps`; nội dung tất định theo `name` và
    chỉ số frame, không phụ thuộc thời gian thực.
    """

    def __init__(
        self,
        clock: Clock,
        fps: float = 10.0,
        payload_size: int = 32,
        name: str = "fake",
    ) -> None:
        if fps <= 0:
            raise ValueError("fps phai > 0")
        if payload_size < 0:
            raise ValueError("payload_size phai >= 0")
        self._clock = clock
        self._fps = float(fps)
        self._payload_size = int(payload_size)
        self._name = str(name)
        self._started = False
        self._t0 = 0.0
        self._index = 0

    @property
    def started(self) -> bool:
        return self._started

    @property
    def frames_emitted(self) -> int:
        return self._index

    def start(self) -> None:
        if self._started:
            raise MediaError("FakeSource da start")
        self._started = True
        self._t0 = self._clock.monotonic()
        self._index = 0

    def read_frame(self, timeout: float = 0.0) -> tuple[float, bytes] | None:
        if not self._started:
            raise MediaError("FakeSource chua start")
        if timeout < 0:
            raise ValueError("timeout am")
        next_ts = self._t0 + self._index / self._fps
        now = self._clock.monotonic()
        if now + 1e-9 < next_ts:
            if timeout <= 0:
                return None
            self._clock.sleep(min(float(timeout), next_ts - now))
            now = self._clock.monotonic()
            if now + 1e-9 < next_ts:
                return None
        pts = next_ts
        index = self._index
        self._index += 1
        payload = bytes(
            (index * 31 + offset) & 0xFF for offset in range(self._payload_size)
        )
        data = f"{self._name}:{index:08d}:".encode("ascii") + payload
        return pts, data

    def stop(self) -> None:
        self._started = False


class RkMpiSource:
    """Nguồn hình thật dùng RK MPI của SDK Rockchip — **chưa hiện thực**.

    Không giả vờ chạy camera: mọi thao tác đều ném `NotImplementedError` kèm
    hướng dẫn. Cần `rk_mpi.h`, cấu hình VI/VPSS/VENC và board Core1106 thật;
    xem docs/14 §4.3 và docs/08.
    """

    _MESSAGE = (
        "RkMpiSource chua hien thuc: can SDK RK MPI (rk_mpi.h, VI/VPSS/VENC) "
        "va board Core1106 that. Xem docs/14 muc 4.3 - CHUA XAC MINH."
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        # Nhận tham số để chỗ nối dây không phải đổi chữ ký khi có SDK.
        self._args = args
        self._kwargs = kwargs

    def start(self) -> None:
        raise NotImplementedError(self._MESSAGE)

    def read_frame(self, timeout: float) -> tuple[float, bytes] | None:
        raise NotImplementedError(self._MESSAGE)

    def stop(self) -> None:
        raise NotImplementedError(self._MESSAGE)
