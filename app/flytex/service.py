"""Ghép tất cả module thành tiến trình `flytex-device`.

`DeviceService` nhận mọi phụ thuộc qua constructor (identity, config, clock,
MCU, modem, media, recorder, queue, publisher, router, diagnostics) để test
được không cần phần cứng. `boot()` bắt tay MCU, phục hồi thẻ nhớ và gửi bản
tin `boot`/`status`; `step(now)` chạy máy trạng thái nguồn, ghi frame, đẩy
hàng đợi và xử lý lệnh MQTT.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import APP_VERSION, mqtt_gen
from .clock import Clock, ClockError
from .cloud import CloudError, Publisher
from .commands import CommandError, CommandRouter
from .config import Config, ConfigError, validate_schedule
from .diagnostics import Diagnostics, DiagnosticsError
from .identity import Identity
from .mcu import McuClient, McuError, ProtocolMismatch
from .media import MediaError, MediaSource
from .modem import AtClient, AtError, AtTimeout
from .power import Busy, PowerConfig, PowerController, PowerState
from .recorder import RawMuxer, RecorderError, SegmentRecorder
from .uplink import UplinkError, UplinkQueue

__all__ = ["DeviceService", "ServiceError"]


class ServiceError(Exception):
    """Lỗi ghép nối/khởi động dịch vụ."""


class DeviceService:
    """Một tiến trình chứa toàn bộ module ứng dụng."""

    BATTERY_PERIOD_S = 300.0
    TEMP_PERIOD_S = 600.0
    CONNECT_RETRY_S = 30.0
    MAX_PUBLISH_PER_STEP = 20
    MAX_FRAMES_PER_STEP = 16

    def __init__(
        self,
        identity: Identity,
        config: Config,
        clock: Clock,
        mcu: McuClient,
        modem: AtClient,
        media: MediaSource,
        recorder: SegmentRecorder,
        queue: UplinkQueue,
        publisher: Publisher,
        router: CommandRouter,
        diagnostics: Diagnostics,
        *,
        config_path: str | os.PathLike[str] | None = None,
    ) -> None:
        if isinstance(recorder.muxer, RawMuxer) and not config.allow_raw_muxer:
            raise ServiceError(
                "config.allow_raw_muxer=False nhung recorder dung RawMuxer; "
                "can muxer container that"
            )
        self.identity = identity
        self.config = config
        self.clock = clock
        self.mcu = mcu
        self.modem = modem
        self.media = media
        self.recorder = recorder
        self.queue = queue
        self.publisher = publisher
        self.router = router
        self.diagnostics = diagnostics
        self.config_path = Path(config_path) if config_path is not None else None
        self.sleep_requested = False
        self.power = PowerController(
            mcu,
            clock,
            recorder,
            queue,
            PowerConfig(
                clip_s=config.clip_s,
                live_s=config.live_s,
                settle_s=config.settle_s,
                mode=config.mode,
            ),
            on_sleep=self._on_power_sleep,
        )
        self.reboot_requested = False
        self._booted = False
        self._start_mono: float | None = None
        self._media_active = False
        self._subscribed = False
        self._next_connect_at = 0.0
        self._next_battery_at = 0.0
        self._next_temp_at = 0.0
        self._shutdown_handled = False
        self._last_state: PowerState | None = None
        self._last_mode: str | None = None
        self._register_default_handlers()

    # -- trạng thái công khai -----------------------------------------
    @property
    def booted(self) -> bool:
        return self._booted

    @property
    def live_url(self) -> str | None:
        """URL relay suy ra từ `config.relay_url` + device id (không cần server)."""
        base = self.config.relay_url.strip()
        if not base:
            return None
        return f"{base.rstrip('/')}/{self.identity.device_id}"

    # -- boot ----------------------------------------------------------
    def boot(self) -> None:
        """Bắt tay MCU, phục hồi thẻ nhớ, gửi boot/status."""
        if self._booted:
            return
        deadline = self.clock.monotonic() + self.power.config.boot_timeout_s
        reason = "unknown"
        while True:
            try:
                self.mcu.check_protocol()
                reason = self.mcu.boot_reason()
                break
            except ProtocolMismatch as exc:
                self.diagnostics.log("error", f"giao thuc MCU khong tuong thich: {exc}")
                raise
            except McuError as exc:
                if self.clock.monotonic() >= deadline:
                    self.diagnostics.log("error", f"MCU khong tra loi: {exc}")
                    raise
                self.diagnostics.log("warning", f"MCU chua san sang: {exc}")
                self.clock.sleep(0.2)
        boot_count = self.diagnostics.record_boot(reason)
        self.mcu.cmd("SOC_WAKE")
        try:
            report = self.recorder.recover()
        except RecorderError as exc:
            self.diagnostics.log("error", f"recover the nho loi: {exc}")
        else:
            if report.removed_parts or report.dropped_index_lines:
                self.diagnostics.log(
                    "warning",
                    "recover: parts="
                    f"{len(report.removed_parts)} index_lines="
                    f"{report.dropped_index_lines} clips={report.clips}",
                )
        self._start_mono = self.clock.monotonic()
        connected = self._connect()
        self._enqueue_boot(reason, boot_count)
        self._enqueue_status()
        self._last_state = self.power.state
        self._last_mode = self.power.mode
        now = self.clock.now()
        self._next_battery_at = now + self.BATTERY_PERIOD_S
        self._next_temp_at = now + self.TEMP_PERIOD_S
        self._flush_queue(now)
        self._booted = True
        self.diagnostics.log(
            "info",
            f"boot xong reason={reason} count={boot_count} mqtt={connected}",
        )

    def _connect(self) -> bool:
        try:
            self.publisher.connect()
        except CloudError as exc:
            self.diagnostics.log("warning", f"khong ket noi duoc cloud: {exc}")
            return False
        if not self.publisher.connected:
            self.diagnostics.log("warning", "publisher khong o trang thai ket noi")
            return False
        if not self._subscribed:
            try:
                self.publisher.subscribe(
                    mqtt_gen.cmd_topic(self.identity.device_id), self._on_command
                )
            except CloudError as exc:
                self.diagnostics.log("error", f"khong subscribe duoc lenh: {exc}")
                return False
            self._subscribed = True
        return True

    # -- vòng chạy -----------------------------------------------------
    def step(self, now: float) -> None:
        """Một nhịp xử lý; không chặn quá lâu."""
        if not self._booted:
            self.boot()
        moment = float(now)
        try:
            self.power.tick(moment)
        except McuError as exc:
            self.diagnostics.log("error", f"MCU tick loi: {exc}")
        else:
            self._after_power_tick()
        if self.power.shutdown_requested:
            self._handle_shutdown()
        self._sync_media()
        if self.power.recording:
            self._pump_frames()
        self._periodic(moment)
        if not self.publisher.connected and moment >= self._next_connect_at:
            self._next_connect_at = moment + self.CONNECT_RETRY_S
            if self._connect():
                self.diagnostics.log("info", "ket noi lai cloud thanh cong")
        self._flush_queue(moment)
        try:
            self.publisher.loop(moment)
        except CloudError as exc:
            self.diagnostics.log("warning", f"MQTT loop loi: {exc}")

    def run_forever(
        self,
        max_seconds: float | None = None,
        *,
        step_s: float = 1.0,
    ) -> None:
        """Chạy tới khi bị dừng, shutdown, reboot hoặc hết `max_seconds`."""
        if step_s <= 0:
            raise ValueError("step_s phai > 0")
        if max_seconds is not None and max_seconds < 0:
            raise ValueError("max_seconds phai >= 0")
        if not self._booted:
            self.boot()
        start = self.clock.monotonic()
        while True:
            elapsed = self.clock.monotonic() - start
            if max_seconds is not None and elapsed >= max_seconds:
                return
            self.step(self.clock.now())
            if (
                self.reboot_requested
                or self.power.shutdown_requested
                or self.sleep_requested
            ):
                return
            sleep_for = step_s
            if max_seconds is not None:
                sleep_for = min(step_s, max_seconds - (self.clock.monotonic() - start))
            if sleep_for > 0:
                self.clock.sleep(sleep_for)

    def stop(self) -> None:
        """Dừng mềm (dùng cho sim/CLI): đóng media và clip đang ghi."""
        if self._media_active:
            try:
                self.media.stop()
            except MediaError as exc:
                self.diagnostics.log("warning", f"dung media loi: {exc}")
            self._media_active = False
        if self.power.recording:
            try:
                self.power.abort_record()
            except (RecorderError, McuError) as exc:
                self.diagnostics.log("error", f"dong clip loi: {exc}")

    # -- sau khi tick nguồn -------------------------------------------
    def _after_power_tick(self) -> None:
        state = self.power.state
        mode = self.power.mode
        if state != self._last_state or mode != self._last_mode:
            self.diagnostics.log("info", f"trang thai {self._last_state} -> {state}")
            self._last_state = state
            self._last_mode = mode
            self._enqueue_status()

    def _on_power_sleep(self) -> None:
        """SoC chuẩn bị ngủ: đồng bộ hàng đợi rồi bảo MCU cắt rail.

        Không có lệnh riêng cho "SoC xin ngủ"; hợp đồng dùng
        `CMD = SOC_SHUTDOWN_DONE` (docs/03 §5, docs/15 §2.5). Firmware hiện tại
        chỉ cắt rail khi MCU đang ở trạng thái SHUTDOWN, nên hành vi cắt rail
        sau clip là CHƯA XÁC MINH trên board thật; app vẫn phải báo.
        """
        if self.sleep_requested:
            return
        self.diagnostics.log("info", "vao che do ngu: bao MCU cat rail")
        self._flush_queue(self.clock.now())
        try:
            self.mcu.cmd("SOC_SHUTDOWN_DONE")
        except McuError as exc:
            self.diagnostics.log("error", f"bao MCU cat rail loi: {exc}")
            return
        self.sleep_requested = True

    # -- media ---------------------------------------------------------
    def _sync_media(self) -> None:
        want = self.power.recording
        if want and not self._media_active:
            try:
                self.media.start()
            except (MediaError, NotImplementedError) as exc:
                self.diagnostics.log("error", f"khong mo duoc nguon hinh: {exc}")
                try:
                    self.power.abort_record()
                except (RecorderError, McuError) as stop_exc:
                    self.diagnostics.log("error", f"dong clip loi: {stop_exc}")
                return
            self._media_active = True
        elif not want and self._media_active:
            try:
                self.media.stop()
            except (MediaError, NotImplementedError) as exc:
                self.diagnostics.log("warning", f"dung media loi: {exc}")
            self._media_active = False

    def _pump_frames(self) -> None:
        if not self._media_active:
            return
        for _ in range(self.MAX_FRAMES_PER_STEP):
            try:
                frame = self.media.read_frame(0.0)
            except (MediaError, NotImplementedError) as exc:
                self.diagnostics.log("error", f"doc frame loi: {exc}")
                return
            if frame is None:
                return
            pts, data = frame
            try:
                self.recorder.write(pts, data)
            except RecorderError as exc:
                self.diagnostics.log("error", f"ghi clip loi: {exc}")
                try:
                    self.power.abort_record()
                except (RecorderError, McuError) as stop_exc:
                    self.diagnostics.log("error", f"dong clip loi: {stop_exc}")
                if self._media_active:
                    try:
                        self.media.stop()
                    except (MediaError, NotImplementedError):
                        pass
                    self._media_active = False
                return

    # -- định kỳ -------------------------------------------------------
    def _periodic(self, now: float) -> None:
        if now >= self._next_battery_at:
            self._next_battery_at = now + self.BATTERY_PERIOD_S
            try:
                self._enqueue_battery()
            except McuError as exc:
                self.diagnostics.log("error", f"doc pin loi: {exc}")
        if now >= self._next_temp_at:
            self._next_temp_at = now + self.TEMP_PERIOD_S
            try:
                self._enqueue_temp()
            except McuError as exc:
                self.diagnostics.log("error", f"doc nhiet do loi: {exc}")

    def _enqueue_battery(self) -> None:
        status = self.mcu.status()
        chg = self.mcu.chg()
        batt = self.mcu.battery_mv()
        self._enqueue(
            {
                "type": "battery",
                "batt_mv": int(batt),
                "batt_pct": None,
                "charging": bool(chg.get("CHARGING", False)),
                "vbus": bool(status.get("VBUS_PRESENT", False)),
                "low": bool(status.get("LOW_BATT", False)),
            },
            "battery",
        )

    def _enqueue_temp(self) -> None:
        batt_c, amb_c = self.mcu.temps()
        self._enqueue(
            {
                "type": "temp",
                "soc_c": None,
                "amb_c": amb_c,
                "batt_c": batt_c,
            },
            "temp",
        )

    def request_status(self) -> None:
        """Xếp bản tin status retained (dùng cho lệnh `status.get`)."""
        self._enqueue_status()

    def _enqueue_status(self) -> None:
        try:
            payload = self._status_payload()
        except McuError as exc:
            self.diagnostics.log("error", f"khong tao duoc status: {exc}")
            return
        self._enqueue(payload, "status")

    def _status_payload(self) -> dict[str, object]:
        status = self.mcu.status()
        batt = self.mcu.battery_mv()
        rssi: int | None = None
        try:
            rssi = self.modem.signal_dbm()
        except (AtError, AtTimeout) as exc:
            self.diagnostics.log("warning", f"khong doc duoc CSQ: {exc}")
        return {
            "type": "status",
            "mode": self.power.mode,
            "state": self.power.state.value,
            "fw": APP_VERSION,
            "mcu_fw": self.mcu.fw_version,
            "proto": self.mcu.proto_version,
            "rssi_dbm": rssi,
            # Chua co AT+QENG de doc bang tan; tra null thay vi doan.
            "band": None,
            "uptime_s": self._uptime_s(),
            "batt_mv": int(batt),
            "sd_free_mb": self.recorder.free_mb(),
            "wake_chan": self.config.wake_chan,
            "live_url": self.live_url if self.power.live else None,
        }

    def _uptime_s(self) -> int:
        if self._start_mono is None:
            return 0
        return max(0, int(self.clock.monotonic() - self._start_mono))

    def _enqueue_boot(self, reason: str, boot_count: int) -> None:
        self._enqueue(
            {
                "type": "boot",
                "reason": reason,
                "sw": APP_VERSION,
                "boot_count": boot_count,
            },
            "status",
        )

    # -- hàng đợi ------------------------------------------------------
    def _enqueue(self, message: dict, priority: str) -> None:
        try:
            evicted = self.queue.enqueue(message, priority)
        except UplinkError as exc:
            self.diagnostics.log("error", f"khong dua vao hang doi: {exc}")
            return
        if evicted:
            self.diagnostics.log(
                "warning", f"hang doi day, da bo ban tin {evicted}"
            )

    def _flush_queue(self, now: float) -> int:
        if not self.publisher.connected:
            return 0
        sent = 0
        for _ in range(self.MAX_PUBLISH_PER_STEP):
            message = self.queue.peek(now)
            if message is None:
                break
            message_id = str(message.get("id", ""))
            if not message_id:
                self.diagnostics.log("error", "ban tin thieu id, bo qua")
                break
            topic = self._topic_for(message)
            payload = self._encode_message(message)
            retain = self._retain_for(message)
            try:
                self.publisher.publish(
                    topic, payload, qos=mqtt_gen.QOS_DEFAULT, retain=retain
                )
            except CloudError as exc:
                self.diagnostics.log("warning", f"publish loi: {exc}")
                try:
                    self.queue.retry_later(message_id, str(exc))
                except UplinkError as queue_exc:
                    self.diagnostics.log("error", f"retry loi: {queue_exc}")
                break
            try:
                self.queue.mark_sent(message_id)
            except UplinkError as exc:
                self.diagnostics.log("error", f"khong ack duoc ban tin: {exc}")
                break
            sent += 1
        return sent

    def _topic_for(self, message: dict) -> str:
        kind = message.get("type")
        if kind == "status":
            return mqtt_gen.status_topic(self.identity.device_id)
        if kind == "ack":
            return mqtt_gen.ack_topic(self.identity.device_id)
        return mqtt_gen.event_topic(self.identity.device_id)

    @staticmethod
    def _retain_for(message: dict) -> bool:
        kind = str(message.get("type", ""))
        return bool(mqtt_gen.EVENT_RETAIN.get(kind, False))

    def _encode_message(self, message: dict) -> bytes:
        payload = dict(message)
        payload.setdefault("v", mqtt_gen.VERSION)
        payload.setdefault("dev", self.identity.device_id)
        if not isinstance(payload.get("ts"), int):
            payload["ts"] = int(self.clock.now())
        return json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

    # -- lệnh MQTT -----------------------------------------------------
    def _on_command(self, topic: str, payload: bytes) -> None:
        if topic != mqtt_gen.cmd_topic(self.identity.device_id):
            self.diagnostics.log("warning", f"bo qua lenh sai topic: {topic}")
            return
        try:
            result = self.router.dispatch(payload)
        except Exception as exc:  # noqa: BLE001 - callback broker không được chết
            self.diagnostics.log("error", f"dispatch loi: {exc}")
            return
        if result is None:
            self.diagnostics.log("warning", "payload khong phai lenh, bo qua")
            return
        ack_topic, ack_payload = result
        try:
            self.publisher.publish(ack_topic, ack_payload, qos=1, retain=False)
        except CloudError as exc:
            self.diagnostics.log("error", f"khong gui duoc ack: {exc}")
            try:
                ack_message = json.loads(ack_payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            if isinstance(ack_message, dict):
                self._enqueue(ack_message, "status")

    # -- shutdown ------------------------------------------------------
    def _handle_shutdown(self) -> None:
        if self._shutdown_handled:
            return
        self._shutdown_handled = True
        self.sleep_requested = True
        if self._media_active:
            try:
                self.media.stop()
            except (MediaError, NotImplementedError) as exc:
                self.diagnostics.log("warning", f"dung media khi tat loi: {exc}")
            self._media_active = False
        reason = self.power.shutdown_reason or "fault"
        batt = (
            self.power.shutdown_batt_mv
            if self.power.shutdown_batt_mv is not None
            else 0
        )
        try:
            self.diagnostics.record_shutdown(reason, batt)
        except DiagnosticsError as exc:
            self.diagnostics.log("error", f"ghi shutdown loi: {exc}")
        self._flush_queue(self.clock.now())
        self.diagnostics.log(
            "info", f"tat an toan reason={reason} batt_mv={batt}"
        )

    # -- handler chuẩn -------------------------------------------------
    def _register_default_handlers(self) -> None:
        handlers = {
            "live.start": self._cmd_live_start,
            "live.stop": self._cmd_live_stop,
            "mode.set": self._cmd_mode_set,
            "schedule.set": self._cmd_schedule_set,
            "time.sync": self._cmd_time_sync,
            "status.get": self._cmd_status_get,
            "config.set": self._cmd_config_set,
            "clip.request": self._cmd_clip_request,
            "reboot": self._cmd_reboot,
        }
        for name, handler in handlers.items():
            if not self.router.has(name):
                self.router.register(name, handler)

    def _cmd_live_start(self, params: dict) -> dict:
        duration = int(params.get("duration_s", self.config.live_s))
        url = self.live_url
        if url is None:
            raise CommandError("NOT_IMPLEMENTED", "chua cau hinh relay_url")
        try:
            self.power.request_live(duration)
        except Busy as exc:
            raise CommandError("BUSY", str(exc)) from exc
        self.diagnostics.log("info", f"live {duration}s url={url}")
        return {"live_url": url, "expires_s": duration}

    def _cmd_live_stop(self, params: dict) -> dict:
        self.power.stop_live()
        return {}

    def _cmd_mode_set(self, params: dict) -> dict:
        try:
            self.power.set_mode(str(params["mode"]))
        except Busy as exc:
            raise CommandError("BUSY", str(exc)) from exc
        except ValueError as exc:
            raise CommandError("BAD_ARGS", str(exc)) from exc
        self.config.mode = self.power.mode
        self._save_config()
        self._enqueue_status()
        return {"mode": self.power.mode}

    def _cmd_schedule_set(self, params: dict) -> dict:
        try:
            entries = validate_schedule(params["entries"])
        except ConfigError as exc:
            raise CommandError("BAD_ARGS", str(exc)) from exc
        self.config.schedule = [dict(entry) for entry in entries]
        self._save_config()
        self.diagnostics.log("info", f"schedule: {len(entries)} muc")
        return {"count": len(entries)}

    def _cmd_time_sync(self, params: dict) -> dict:
        target = int(params["ts"])
        offset = float(target) - self.clock.now()
        setter = getattr(self.clock, "set_now", None)
        if not callable(setter):
            raise CommandError(
                "NOT_IMPLEMENTED", "clock khong ho tro dat gio he thong"
            )
        try:
            setter(target)
        except ClockError as exc:
            raise CommandError("INTERNAL", str(exc)) from exc
        self.diagnostics.log("info", f"time.sync offset={offset:.3f}s")
        return {"offset_s": round(offset, 3), "applied": True}

    def _cmd_status_get(self, params: dict) -> dict:
        self.request_status()
        return {}

    def _cmd_config_set(self, params: dict) -> dict:
        key = str(params["key"])
        value = params["value"]
        try:
            converted = self.config.set_allowed(key, value)
        except ConfigError as exc:
            raise CommandError("BAD_ARGS", str(exc)) from exc
        self._save_config()
        self.diagnostics.log("info", f"config.set {key}={converted!r}")
        return {"key": key, "value": converted}

    def _cmd_clip_request(self, params: dict) -> dict:
        raise CommandError(
            "NOT_IMPLEMENTED", "tai clip len kho (HTTP upload) chua hien thuc"
        )

    def _cmd_reboot(self, params: dict) -> dict:
        self.reboot_requested = True
        self.diagnostics.log("warning", "reboot duoc yeu cau")
        # run_forever thoát; init/systemd chịu trách nhiệm khởi động lại tiến
        # trình. Khởi động lại cả hệ thống CHƯA XÁC MINH trên SDK.
        return {"reboot": "requested"}

    def _save_config(self) -> None:
        if self.config_path is None:
            return
        try:
            self.config.save(self.config_path)
        except ConfigError as exc:
            raise CommandError("INTERNAL", str(exc)) from exc
