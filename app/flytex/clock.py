"""Đồng hồ tiêm được cho ứng dụng Linux.

Mã nghiệp vụ không bao giờ gọi thẳng `time.sleep` hay `time.time`; mọi thứ đi
qua `Clock`. Test dùng `FakeClock` để chạy tức thì và không flaky, kể cả khi
kiểm tra timeout của modem hay hết hạn ghi hình.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


class ClockError(Exception):
    """Không đặt được giờ hệ thống (thiếu quyền hoặc nền tảng không hỗ trợ)."""


@runtime_checkable
class Clock(Protocol):
    """Đồng hồ tối thiểu mà ứng dụng cần."""

    def now(self) -> float:
        """Unix time (giây), dùng cho timestamp bản tin và hạn theo lịch."""

    def monotonic(self) -> float:
        """Đồng hồ đơn điệu (giây), dùng cho timeout và độ dài clip."""

    def sleep(self, seconds: float) -> None:
        """Ngủ `seconds`; `RealClock` ngủ thật, `FakeClock` chỉ dịch giờ."""


class RealClock:
    """Đồng hồ thật dùng module `time`."""

    def now(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def set_now(self, ts: float) -> None:
        """Đặt giờ hệ thống nếu nền tảng cho phép.

        Trên Linux cần quyền root; trên Windows không có `time.clock_settime`
        nên `ClockError` được ném ra thay vì giả vờ thành công.
        """

        setter = getattr(time, "clock_settime", None)
        if setter is None:
            raise ClockError("nen tang khong ho tro dat gio he thong")
        try:
            setter(getattr(time, "CLOCK_REALTIME", 0), float(ts))
        except (OSError, OverflowError, ValueError) as exc:
            raise ClockError(f"khong dat duoc gio he thong: {exc}") from exc


class FakeClock:
    """Đồng hồ giả: `sleep` chỉ dịch thời gian, không chặn.

    `now` là giờ thực (Unix time), `monotonic` là đồng hồ đơn điệu. `advance`
    dịch cả hai, còn `set_now` chỉ đổi giờ thực (mô phỏng đồng bộ giờ từ cloud).
    """

    def __init__(self, start: float = 0.0, mono: float = 0.0) -> None:
        self._now = float(start)
        self._mono = float(mono)

    def now(self) -> float:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep voi so giay am")
        self._now += float(seconds)
        self._mono += float(seconds)

    def advance(self, seconds: float) -> None:
        """Dịch cả giờ thực và đồng hồ đơn điệu."""
        if seconds < 0:
            raise ValueError("advance voi so giay am")
        self.sleep(seconds)

    def set_now(self, ts: float) -> None:
        """Đặt giờ thực, không đổi đồng hồ đơn điệu."""
        self._now = float(ts)

    def set_monotonic(self, value: float) -> None:
        """Đặt đồng hồ đơn điệu (dùng khi test cần mốc cụ thể)."""
        self._mono = float(value)

    def __repr__(self) -> str:  # pragma: no cover - chỉ để đọc log
        return f"FakeClock(now={self._now!r}, mono={self._mono!r})"
