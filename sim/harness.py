"""Khung dựng cho kịch bản mô phỏng: firmware thật + ứng dụng thật + đồng hồ giả."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any, Callable

from flytex.mcu import McuClient
from flytex.power import PowerConfig, PowerController
from flytex.recorder import SegmentRecorder
from flytex.tsmux import TsMuxer
from flytex.uplink import UplinkQueue

from .clock import SimClock, SocEmulator
from .ffi import (
    ADC_VBAT,
    PIN_IRQ,
    PIN_MODEM_PWR,
    PIN_MODEM_STATUS,
    PIN_PIR,
    PIN_SOC_PWR,
    PIN_SOC_READY,
    PIN_VBUS,
    TEMP_AMB,
    TEMP_BATT,
    McuSim,
)
from .link import FfiMcuLink

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "sim" / "build"


class ScenarioFailure(AssertionError):
    """Một bất biến của kịch bản bị vi phạm."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioFailure(message)


class SimRig:
    """Một thiết bị mô phỏng: MCU C thật, SoC giả, ứng dụng thật."""

    def __init__(
        self,
        workdir: Path,
        *,
        mode: str = "eco",
        clip_s: float = 3.0,
        live_s: float = 5.0,
        settle_s: float = 1.0,
        adc_mv: int = 1650,
        batt_c: int = 25,
        amb_c: int = 22,
        step_ms: int = 250,
    ) -> None:
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        self.workdir = workdir
        self.states: list[str] = []
        self.log: list[str] = []

        self.sim = McuSim()
        self.clock = SimClock(self.sim, step_ms=step_ms)
        self.soc = SocEmulator(self.sim)
        self.soc.attach(self.clock)
        self.link = FfiMcuLink(self.sim, self.clock)
        self.mcu = McuClient(self.link)
        self.mcu.check_protocol()
        self.mcu.set_mode(mode)

        self.sim.set_adc_mv(ADC_VBAT, adc_mv)
        self.sim.set_temp_c(TEMP_BATT, batt_c)
        self.sim.set_temp_c(TEMP_AMB, amb_c)
        self.sim.set_input(PIN_VBUS, 0)
        self.sim.set_input(PIN_PIR, 0)

        self.recorder = SegmentRecorder(
            workdir / "clips",
            self.clock,
            TsMuxer(),
            segment_s=4.0,
            max_bytes=8 * 1024 * 1024,
            pin_budget_bytes=4 * 1024 * 1024,
        )
        self.queue = UplinkQueue(
            workdir / "queue.jsonl",
            self.clock,
            max_bytes=2 * 1024 * 1024,
            rng=random.Random(1234),
        )
        self.controller = PowerController(
            self.mcu,
            self.clock,
            self.recorder,
            self.queue,
            PowerConfig(
                clip_s=clip_s,
                live_s=live_s,
                settle_s=settle_s,
                mode=mode,
            ),
        )
        self.frame_index = 0

    # -- điều khiển -----------------------------------------------------
    def advance(self, seconds: float, frames: bool = True) -> None:
        steps = max(1, int(round(seconds / 0.5)))
        for _ in range(steps):
            self.clock.advance(0.5)
            if frames and self.recorder.recording:
                payload = f"frame-{self.frame_index:05d}".encode()
                self.recorder.write(self.frame_index * 0.5, payload)
                self.frame_index += 1
            self.tick()

    def tick(self) -> None:
        self.controller.tick(self.clock.now())
        state = self.controller.state.value
        if not self.states or self.states[-1] != state:
            self.states.append(state)
            self.log.append(f"state -> {state} at t={self.clock.monotonic():.1f}s")

    def wait_for(self, predicate: Callable[[], bool], timeout_s: float, what: str) -> None:
        deadline = self.clock.monotonic() + timeout_s
        while True:
            if predicate():
                return
            if self.clock.monotonic() >= deadline:
                raise ScenarioFailure(f"quá {timeout_s:.0f}s chưa {what}")
            self.clock.advance(0.25)

    def wake_by_pir(self) -> None:
        self.sim.set_input(PIN_PIR, 1)
        self.clock.advance(0.4)
        self.sim.set_input(PIN_PIR, 0)
        self.wait_for(lambda: self.sim.get_output(PIN_SOC_PWR) == 1, 5.0, "bật rail SoC")
        self.wait_for(lambda: self.soc.soc_ready, 5.0, "SoC báo READY")
        self.mcu.cmd("SOC_WAKE")
        self.tick()

    # -- kết quả --------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        return self.sim.stats()

    def report(self, scenario: str, passed: bool, detail: str = "") -> dict[str, Any]:
        return {
            "scenario": scenario,
            "passed": passed,
            "detail": detail,
            "states": self.states,
            "log": self.log,
            "stats": self.stats(),
            "final_state": self.controller.state.value,
            "queue_pending": len(self.queue),
            "clips": [clip.clip_id for clip in self.recorder.list_clips()],
            "sim_time_s": round(self.clock.monotonic(), 2),
        }

    def write_report(self, scenario: str, passed: bool, detail: str = "") -> Path:
        BUILD.mkdir(parents=True, exist_ok=True)
        path = BUILD / f"report-{scenario}.json"
        path.write_text(
            json.dumps(self.report(scenario, passed, detail), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def close(self) -> None:
        try:
            if self.recorder.recording:
                self.recorder.stop()
        except Exception:  # noqa: BLE001 - đóng dở khi kết thúc kịch bản
            pass
        self.mcu.close()
        self.sim.close()
