"""Cầu nối McuLink của ứng dụng sang firmware C đang chạy trong bộ nhớ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ffi import PIN_IRQ, McuSim

if TYPE_CHECKING:
    from .clock import SimClock


def _nack(message: str) -> Exception:
    """Trả đúng loại lỗi mà ứng dụng bắt, nếu app đã import được."""
    try:
        from flytex.mcu import McuNack  # type: ignore import-not-found

        return McuNack(message)
    except Exception:  # noqa: BLE001 - app có thể chưa có trong sys.path
        return OSError(message)


class FfiMcuLink:
    """Hiện thực McuLink trên firmware C thật."""

    def __init__(self, sim: McuSim, clock: "SimClock") -> None:
        self._sim = sim
        self._clock = clock
        self.closed = False

    def read(self, addr: int, n: int = 1) -> bytes:
        if self.closed:
            raise _nack("link đã đóng")
        try:
            return self._sim.i2c_read(addr, n)
        except OSError as exc:
            raise _nack(str(exc)) from exc

    def write(self, addr: int, data: bytes) -> None:
        if self.closed:
            raise _nack("link đã đóng")
        try:
            self._sim.i2c_write(addr, data)
        except OSError as exc:
            raise _nack(str(exc)) from exc

    def irq_wait(self, timeout: float) -> bool:
        deadline = self._clock.monotonic() + max(0.0, float(timeout))
        while True:
            if self._sim.get_output(PIN_IRQ) == 0:
                return True
            remaining = deadline - self._clock.monotonic()
            if remaining <= 0:
                return False
            self._clock.sleep(min(0.02, remaining))

    def close(self) -> None:
        self.closed = True
