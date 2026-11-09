"""Máy trạng thái nguồn của ứng dụng Linux.

Trạng thái giống docs/04 §3.2: S0 Eco, S1 Watch, S2 Record, S3 Live, SF Fault.
Điểm quan trọng: sau khi hết clip, hệ thống về **chế độ ngủ đã cấu hình**
(Eco hoặc Watch), không mặc định về Eco như CAM4G.

Mọi thời gian đi qua `Clock`; test dùng `FakeClock` nên không ngủ thật.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .clock import Clock
from .mcu import McuClient, McuError
from .recorder import ClipInfo, RecorderError, SegmentRecorder
from .uplink import UplinkQueue


class PowerState(str, Enum):
    """Trạng thái nguồn; giá trị chuỗi trùng enum `state` của MQTT."""

    S0_ECO = "s0"
    S1_WATCH = "s1"
    S2_RECORD = "s2"
    S3_LIVE = "s3"
    SF_FAULT = "sf"


class PowerError(Exception):
    """Lỗi máy trạng thái nguồn."""


class Busy(PowerError):
    """Từ chối thao tác vì đang ghi hoặc đang live (ack `BUSY`)."""

    ack_code = "BUSY"


_SLEEP_STATE = {
    "eco": PowerState.S0_ECO,
    "watch": PowerState.S1_WATCH,
}


@dataclass
class PowerConfig:
    """Tham số máy trạng thái (giây).

    `mode` là chế độ ngủ đã cấu hình ban đầu; không có trong bảng mặc định
    của docs/04 nhưng cần để khởi tạo đúng trạng thái.
    """

    clip_s: float = 30.0
    settle_s: float = 10.0
    live_s: float = 120.0
    boot_timeout_s: float = 20.0
    max_record_s: float = 600.0
    mode: str = "eco"

    def __post_init__(self) -> None:
        if self.clip_s <= 0:
            raise ValueError("clip_s phai > 0")
        if self.settle_s < 0:
            raise ValueError("settle_s phai >= 0")
        if self.live_s <= 0:
            raise ValueError("live_s phai > 0")
        if self.boot_timeout_s <= 0:
            raise ValueError("boot_timeout_s phai > 0")
        if self.max_record_s <= 0:
            raise ValueError("max_record_s phai > 0")
        if self.mode not in _SLEEP_STATE:
            raise ValueError(f"mode khong hop le: {self.mode!r}")


class PowerController:
    """Máy trạng thái nguồn, điều khiển ghi hình và báo sự kiện lên uplink."""

    def __init__(
        self,
        link: McuClient,
        clock: Clock,
        recorder: SegmentRecorder,
        uplink: UplinkQueue,
        config: PowerConfig | None = None,
        *,
        on_sleep: Callable[[], None] | None = None,
    ) -> None:
        # `link` là McuClient: cần events/fault/status/battery_mv/cmd.
        self._link = link
        self._clock = clock
        self._recorder = recorder
        self._uplink = uplink
        self._on_sleep = on_sleep
        self.config = config if config is not None else PowerConfig()
        self._mode = self.config.mode
        self._state = _SLEEP_STATE[self._mode]
        self._clip: ClipInfo | None = None
        self._active = False
        self._clip_started_mono: float | None = None
        self._clip_ir = False
        self._clip_id: str | None = None
        self._live_until: float | None = None
        self._settle_until: float | None = None
        self._announced_fault: str | None = None
        self._last_batt_mv: int | None = None
        self._shutdown_requested = False
        self._shutdown_done = False
        self.shutdown_reason: str | None = None
        self.shutdown_batt_mv: int | None = None
        self.last_clip: ClipInfo | None = None
        self.last_recorder_error: str | None = None

    # -- trạng thái công khai ------------------------------------------
    @property
    def state(self) -> PowerState:
        return self._state

    @property
    def mode(self) -> str:
        """Chế độ ngủ đã cấu hình (`eco` hoặc `watch`)."""
        return self._mode

    @property
    def recording(self) -> bool:
        return self._active

    @property
    def live(self) -> bool:
        return self._state is PowerState.S3_LIVE

    @property
    def clip_id(self) -> str | None:
        return self._clip_id

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    @property
    def shutdown_done(self) -> bool:
        return self._shutdown_done

    def live_remaining_s(self, now: float) -> float:
        if self._live_until is None:
            return 0.0
        return max(0.0, self._live_until - float(now))

    # -- API điều khiển ------------------------------------------------
    def tick(self, now: float) -> None:
        """Xử lý sự kiện MCU, lỗi và các hạn thời gian tại thời điểm `now`."""
        if self._shutdown_requested:
            return
        moment = float(now)
        events = self._link.events()
        if "SHUTDOWN_REQ" in events:
            self._safe_shutdown(moment)
            return
        status = self._link.status()
        if status.get("LOW_BATT", False) or "LOW_BATT" in events:
            # Docs/04 §2.3: pin dưới ngưỡng cảnh báo thì SoC đóng file và báo
            # SOC_SHUTDOWN_DONE; đây không phải lỗi nhiệt nên không vào SF.
            self._handle_low_battery(moment, status)
            return
        self._refresh_fault(moment, status)
        if self._shutdown_requested:
            return
        for name in ("PIR", "SCHEDULE"):
            if name in events and self._state in (
                PowerState.S0_ECO,
                PowerState.S1_WATCH,
            ):
                self._begin_record(now=moment, ir=False)
                self._state = PowerState.S2_RECORD
                break
        self._advance(moment)

    def request_live(self, duration_s: float | None = None) -> None:
        """Vào S3 trong `duration_s` giây; mặc định theo `config.live_s`."""
        if self._shutdown_requested:
            raise Busy("thiet bi dang tat an toan")
        if self._state is PowerState.SF_FAULT:
            raise Busy("dang o trang thai loi")
        duration = self.config.live_s if duration_s is None else float(duration_s)
        if duration <= 0:
            raise ValueError("duration_s phai > 0")
        now = self._clock.now()
        if self._state in (PowerState.S0_ECO, PowerState.S1_WATCH) or self._state is PowerState.S2_RECORD and not self._active:
            self._begin_record(now=now, ir=False)
        self._live_until = now + duration
        self._settle_until = None
        self._state = PowerState.S3_LIVE

    def stop_live(self, now: float | None = None) -> None:
        """Hủy live (nếu đang live), quay về S2."""
        if self._state is not PowerState.S3_LIVE:
            return
        self._stop_live(self._clock.now() if now is None else float(now))

    def set_mode(self, mode: str) -> None:
        """Đổi chế độ ngủ; bị từ chối khi đang ghi hoặc đang live."""
        if self._state in (PowerState.S2_RECORD, PowerState.S3_LIVE):
            raise Busy("khong doi mode khi dang ghi hoac live")
        key = str(mode).lower()
        if key not in _SLEEP_STATE:
            raise ValueError(f"mode khong hop le: {mode!r}")
        self._link.set_mode(key)
        self._mode = key
        if self._state in (PowerState.S0_ECO, PowerState.S1_WATCH):
            self._state = _SLEEP_STATE[key]

    def abort_record(self) -> ClipInfo | None:
        """Đóng clip hiện tại khi tầng trên gặp lỗi ghi (ví dụ thẻ đầy)."""
        if not self.recording:
            return None
        info = self._stop_recorder()
        self.last_clip = info
        self._clip = info
        self._active = False
        self._clip_started_mono = None
        self._clip_id = None
        if self._state is PowerState.S3_LIVE:
            return info
        self._state = PowerState.S2_RECORD
        self._settle_until = self._clock.now() + self.config.settle_s
        return info

    # -- nội bộ --------------------------------------------------------
    def _handle_low_battery(self, now: float, status: dict[str, bool]) -> None:
        """Pin cạn: báo pin, đóng clip rồi tắt an toàn (idempotent)."""
        if self._shutdown_requested:
            return
        batt: int | None
        try:
            batt = self._read_batt_mv()
        except McuError:
            batt = self._last_batt_mv
        if batt is not None:
            try:
                chg = self._link.chg()
            except McuError:
                chg = {}
            self._uplink.enqueue(
                {
                    "type": "battery",
                    "batt_mv": int(batt),
                    "batt_pct": None,
                    "charging": bool(chg.get("CHARGING", False)),
                    "vbus": bool(status.get("VBUS_PRESENT", False)),
                    "low": True,
                },
                priority="battery",
            )
        self._safe_shutdown(now)

    def _refresh_fault(
        self, now: float, status: dict[str, bool] | None = None
    ) -> None:
        fault = self._link.fault()
        if status is None:
            status = self._link.status()
        if self._state is PowerState.SF_FAULT:
            if fault == "NONE" and not status.get("LOW_BATT", False):
                self._exit_fault()
            elif fault != "NONE" and fault != self._announced_fault:
                self._announced_fault = fault
                self._enqueue_fault(fault, "fault code changed")
            return
        if fault != "NONE":
            self._enter_fault(now, fault)

    def _enter_fault(self, now: float, code: str) -> None:
        detail = f"code={code}"
        if self.recording:
            try:
                info = self._stop_recorder()
                self.last_clip = info
            except RecorderError as exc:
                self.last_recorder_error = str(exc)
                detail += "; recorder_error=" + str(exc)
        self._active = False
        self._clip = None
        self._clip_started_mono = None
        self._clip_id = None
        self._live_until = None
        self._settle_until = None
        self._state = PowerState.SF_FAULT
        self._announced_fault = code
        self._enqueue_fault(code, detail)

    def _exit_fault(self) -> None:
        self._announced_fault = None
        self._state = _SLEEP_STATE[self._mode]

    def _enqueue_fault(self, code: str, detail: str) -> None:
        self._uplink.enqueue(
            {"type": "fault", "code": code, "detail": detail},
            priority="fault",
        )

    def _begin_record(self, now: float, ir: bool) -> None:
        # clip_id là 16 hex theo spec/mqtt.toml (không phải 32 của uuid4 hex).
        clip_id = secrets.token_hex(8)
        self._recorder.start(clip_id, ir=ir)
        self._clip_id = clip_id
        self._clip_started_mono = self._clock.monotonic()
        self._clip_ir = ir
        self._clip = None  # ClipInfo chỉ có sau khi stop
        self._active = True
        self._settle_until = None

    def _advance(self, now: float) -> None:
        if self._active:
            started = self._clip_started_mono
            if started is None:
                started = now
            elapsed = self._clock.monotonic() - started
            if self._state is PowerState.S3_LIVE:
                limit = self.config.max_record_s
            else:
                limit = min(self.config.clip_s, self.config.max_record_s)
            if elapsed >= limit:
                self._finish_clip(now)
        if (
            self._state is PowerState.S3_LIVE
            and self._live_until is not None
            and now >= self._live_until
        ):
            self._stop_live(now)
        if (
            self._state is PowerState.S2_RECORD
            and not self._active
            and self._settle_until is not None
            and now >= self._settle_until
        ):
            self._settle_until = None
            self._state = _SLEEP_STATE[self._mode]
            self._notify_sleep()

    def _finish_clip(self, now: float) -> None:
        batt_mv = self._read_batt_mv()
        info = self._stop_recorder()
        self.last_clip = info
        self._clip = info
        self._active = False
        self._clip_started_mono = None
        self._clip_id = None
        duration = max(0, round(info.duration_s))
        self._uplink.enqueue(
            {
                "type": "motion",
                "clip_id": info.clip_id,
                "duration_s": duration,
                "ir": bool(info.ir),
                "batt_mv": batt_mv,
                "batt_pct": None,
            },
            priority="motion",
        )
        if self._state is not PowerState.S3_LIVE:
            self._state = PowerState.S2_RECORD
            self._settle_until = float(now) + self.config.settle_s

    def _stop_recorder(self) -> ClipInfo:
        info = self._recorder.stop()
        if not isinstance(info, ClipInfo):  # pragma: no cover - bảo vệ hợp đồng
            raise PowerError("recorder.stop phai tra ClipInfo")
        return info

    def _read_batt_mv(self) -> int:
        value = int(self._link.battery_mv())
        self._last_batt_mv = value
        return value

    def _stop_live(self, now: float) -> None:
        self._live_until = None
        self._state = PowerState.S2_RECORD
        if not self._active:
            self._settle_until = float(now) + self.config.settle_s

    def _notify_sleep(self) -> None:
        """Báo tầng trên rằng SoC sắp ngủ (service sẽ bảo MCU cắt rail)."""
        if self._on_sleep is not None:
            self._on_sleep()

    def _shutdown_reason(self) -> str:
        try:
            fault = self._link.fault()
            status = self._link.status()
        except McuError:
            return "fault"
        if fault in ("BATT_OVERTEMP", "BATT_UNDERTEMP"):
            return "thermal"
        if fault == "BATT_UNDERVOLTAGE" or status.get("LOW_BATT"):
            return "low_batt"
        return "user"

    def _safe_shutdown(self, now: float) -> None:
        """Đóng file trước, rồi báo MCU; mất điện tối đa một đoạn."""
        if self._shutdown_requested:
            return
        reason = self._shutdown_reason()
        self.shutdown_reason = reason
        try:
            batt_mv = self._read_batt_mv()
        except McuError:
            batt_mv = self._last_batt_mv if self._last_batt_mv is not None else 0
        self.shutdown_batt_mv = batt_mv
        if self.recording:
            try:
                info = self._stop_recorder()
                self.last_clip = info
            except RecorderError as exc:
                self.last_recorder_error = str(exc)
        self._clip = None
        self._clip_started_mono = None
        self._clip_id = None
        self._live_until = None
        self._settle_until = None
        self._state = PowerState.S0_ECO
        self._shutdown_requested = True
        self._uplink.enqueue(
            {"type": "shutdown", "reason": reason, "batt_mv": batt_mv},
            priority="fault",
        )
        self._link.cmd("SOC_SHUTDOWN_DONE")
        self._shutdown_done = True
