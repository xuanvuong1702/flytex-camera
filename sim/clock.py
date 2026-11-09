"""Đồng hồ mô phỏng dùng chung cho firmware C và ứng dụng Python.

Thời gian chỉ trôi khi có ai đó ngủ/chờ. Mỗi bước trôi đều đẩy firmware tiến lên,
nên hành vi của MCU trong mô phỏng là hành vi của mã C thật.
"""

from __future__ import annotations

from typing import Callable

from .ffi import PIN_MODEM_PWR, PIN_MODEM_STATUS, PIN_SOC_PWR, PIN_SOC_READY, McuSim


class SimClock:
    """Clock theo giao thức của ứng dụng (now/monotonic/sleep)."""

    def __init__(self, sim: McuSim, start_wall: float = 1_700_000_000.0, step_ms: int = 250) -> None:
        self._sim = sim
        self._wall0 = float(start_wall)
        self._mono = 0.0
        self._step_ms = max(1, int(step_ms))
        self._callbacks: list[Callable[["SimClock"], None]] = []

    # -- giao thức Clock ------------------------------------------------
    def now(self) -> float:
        return self._wall0 + self._mono

    def monotonic(self) -> float:
        return self._mono

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    # -- điều khiển thời gian ------------------------------------------
    def advance(self, seconds: float) -> None:
        if seconds <= 0:
            self._run_callbacks()
            return
        remaining_ms = int(round(seconds * 1000.0))
        if remaining_ms <= 0:
            remaining_ms = 1
        while remaining_ms > 0:
            chunk = min(self._step_ms, remaining_ms)
            advanced = self._sim.advance_ms(chunk)
            if advanced <= 0:
                advanced = chunk
            self._mono += advanced / 1000.0
            remaining_ms -= advanced
            self._run_callbacks()

    def set_wall(self, wall: float) -> None:
        self._wall0 = float(wall) - self._mono

    def add_callback(self, callback: Callable[["SimClock"], None]) -> None:
        self._callbacks.append(callback)

    def _run_callbacks(self) -> None:
        for callback in self._callbacks:
            callback(self)


class SocEmulator:
    """Giả lập SoC: báo SOC_READY sau khi có rail, và modem báo STATUS."""

    def __init__(
        self,
        sim: McuSim,
        boot_delay_s: float = 1.5,
        modem_boot_delay_s: float = 3.0,
    ) -> None:
        self._sim = sim
        self._boot_delay = boot_delay_s
        self._modem_delay = modem_boot_delay_s
        self._soc_on_since: float | None = None
        self._modem_on_since: float | None = None
        self.boot_count = 0
        self.modem_boot_count = 0
        self.soc_ready = False
        self.modem_ready = False

    def tick(self, clock: SimClock) -> None:
        now = clock.monotonic()
        soc_power = self._sim.get_output(PIN_SOC_PWR)
        if soc_power:
            if self._soc_on_since is None:
                self._soc_on_since = now
                self.boot_count += 1
            elif now - self._soc_on_since >= self._boot_delay:
                self.soc_ready = True
                self._sim.set_input(PIN_SOC_READY, 1)
        else:
            self._soc_on_since = None
            self.soc_ready = False
            self._sim.set_input(PIN_SOC_READY, 0)

        modem_power = self._sim.get_output(PIN_MODEM_PWR)
        if modem_power:
            if self._modem_on_since is None:
                self._modem_on_since = now
                self.modem_boot_count += 1
            elif now - self._modem_on_since >= self._modem_delay:
                self.modem_ready = True
                self._sim.set_input(PIN_MODEM_STATUS, 1)
        else:
            self._modem_on_since = None
            self.modem_ready = False
            self._sim.set_input(PIN_MODEM_STATUS, 0)

    def attach(self, clock: SimClock) -> None:
        clock.add_callback(self.tick)
