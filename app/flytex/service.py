"""Ghép tất cả module thành tiến trình `flytex-device`.

`DeviceService` nhận mọi phụ thuộc qua constructor (identity, config, clock,
MCU, modem, media, recorder, queue, publisher, router, diagnostics) để test
được không cần phần cứng. `boot()` bắt tay MCU, phục hồi thẻ nhớ và gửi bản
tin `boot`/`status`; `step(now)` chạy máy trạng thái nguồn, ghi frame, đẩy
hàng đợi và xử lý lệnh MQTT.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
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
from .ota import OtaError, OtaManager
from .power import Busy, PowerConfig, PowerController, PowerState
from .recorder import ClipInfo, RawMuxer, RecorderError, SegmentRecorder
from .upload import UploadError, Uploader, UploadSpool
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
        uploader: Uploader | None = None,
        spool: UploadSpool | None = None,
        ota: OtaManager | None = None,
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
        self.uploader = uploader
        self.spool = spool
        self.ota = ota
        if (uploader is None) != (spool is None):
            raise ServiceError("uploader va spool phai duoc cau hinh cung nhau")
        self.sleep_requested = False
        self.wake_sms_ok = False
        self._wake_last_ts = 0
        self._wake_ts_path = (
            self.config_path.parent / "wake_last_ts"
            if self.config_path is not None
            else None
        )
        if self._wake_ts_path is not None and self._wake_ts_path.exists():
            try:
                self._wake_last_ts = int(
                    self._wake_ts_path.read_text(encoding="utf-8").strip()
                )
            except (OSError, ValueError):
                self._wake_last_ts = 0
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
        self._spooled_clip_id: str | None = None
        self._upload_thread: threading.Thread | None = None
        self._upload_done: threading.Event | None = None
        self._upload_item: object | None = None
        self._upload_result: object | None = None
        self._upload_error: Exception | None = None
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
        if self.ota is not None:
            try:
                ota_status = self.ota.check_boot(APP_VERSION)
                if ota_status.state == "rolled_back":
                    self.diagnostics.log("warning", "OTA quay lui vi khong khoi dong duoc")
            except OtaError as exc:
                self.diagnostics.log("error", f"OTA check_boot loi: {exc}")
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
        self._consume_wake_sms()
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
        self._maybe_spool_clip()

    def _maybe_spool_clip(self) -> None:
        """Đưa clip vừa đóng vào hàng đợi tải lên, một lần mỗi clip."""
        if self.spool is None:
            return
        clip = self.power.last_clip
        if clip is None or clip.clip_id == self._spooled_clip_id:
            return
        self._spooled_clip_id = clip.clip_id
        try:
            self.spool.add(clip.clip_id, clip.path, clip.size_b)
        except UploadError as exc:
            self.diagnostics.log("error", f"khong dua clip vao hang doi: {exc}")

    # -- tải clip ------------------------------------------------------
    def _pack_clip(self, clip_id: str, path: str) -> Path:
        """Trả một file .ts để tải: đoạn đơn, hoặc nối các đoạn TS."""
        clip_dir = Path(path)
        segments = sorted(clip_dir.glob("*.ts"))
        if not segments:
            segments = [item for item in sorted(clip_dir.iterdir()) if item.is_file()]
        if not segments:
            raise UploadError(f"clip {clip_id} khong co file")
        if len(segments) == 1:
            return segments[0]
        target = clip_dir / f"{clip_id}.upload.ts"
        with target.open("wb") as handle:
            for segment in segments:
                handle.write(segment.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        return target

    def _try_upload(self, now: float) -> None:
        if self.spool is None or self.uploader is None:
            return
        self._collect_upload()
        if self._upload_thread is not None or self.power.recording:
            return
        item = self.spool.pending(now)
        if item is None:
            return
        try:
            packed = self._pack_clip(item.clip_id, item.path)
        except (UploadError, OSError) as exc:
            self._fail_upload(item_clip_id=item.clip_id, error=exc)
            return
        self._upload_item = item
        self._upload_result = None
        self._upload_error = None
        done = threading.Event()
        self._upload_done = done

        def work() -> None:
            try:
                self._upload_result = self.uploader.upload(packed, item.clip_id)
            except Exception as exc:  # noqa: BLE001 - chuyển lỗi về luồng chính
                self._upload_error = exc
            finally:
                done.set()

        thread = threading.Thread(
            target=work, name=f"upload-{item.clip_id}", daemon=True
        )
        self._upload_thread = thread
        thread.start()

    def _collect_upload(self) -> None:
        thread = self._upload_thread
        done = self._upload_done
        if thread is None or done is None or not done.is_set():
            return
        thread.join(timeout=1.0)
        item = self._upload_item
        result = self._upload_result
        error = self._upload_error
        self._upload_thread = None
        self._upload_done = None
        self._upload_item = None
        self._upload_result = None
        self._upload_error = None
        if item is None:
            return
        if result is not None and error is None:
            self.spool.done(item.clip_id)
            self._enqueue(
                {
                    "type": "clip_ready",
                    "clip_id": item.clip_id,
                    "url": result.url,
                    "size_b": result.size_b,
                },
                "motion",
            )
            self.diagnostics.log(
                "info", f"da tai clip {item.clip_id} ({result.size_b} B)"
            )
        else:
            self._fail_upload(item_clip_id=item.clip_id, error=error or "unknown")

    def _fail_upload(self, *, item_clip_id: str, error: object) -> None:
        delay = self.spool.fail(item_clip_id, error)
        self.diagnostics.log(
            "warning",
            f"tai clip {item_clip_id} loi: {error}"
            + (f", thu lai sau {delay:.0f}s" if delay is not None else ", bo"),
        )

    def _consume_wake_sms(self) -> None:
        """Đọc SMS đánh thức; yêu cầu HMAC, timestamp tươi và chống replay.

        Định dạng: ``W <unix_ts> <hmac16>``. HMAC-SHA256 trên chuỗi timestamp,
        khóa là ``wake_secret`` (hex). Không có secret thì từ chối, không mở.
        """
        if self.config.wake_chan != "sms":
            return
        if not self.config.wake_secret:
            self.diagnostics.log(
                "warning", "SMS danh thuc bi tu choi: chua cau hinh wake_secret"
            )
            return
        try:
            messages = self.modem.sms_read()
        except (AtError, AtTimeout) as exc:
            self.diagnostics.log("warning", f"doc SMS danh thuc loi: {exc}")
            return
        try:
            key = bytes.fromhex(self.config.wake_secret)
        except ValueError:
            self.diagnostics.log(
                "error", "SMS danh thuc bi tu choi: wake_secret khong phai hex"
            )
            return
        if len(key) < 16:
            self.diagnostics.log(
                "error", "SMS danh thuc bi tu choi: wake_secret qua ngan"
            )
            return
        now = int(self.clock.now())
        for message in messages:
            parts = message.text.strip().split()
            if len(parts) != 3 or parts[0] != "W":
                continue
            try:
                ts = int(parts[1])
            except ValueError:
                continue
            if abs(now - ts) > 600:
                self.diagnostics.log("warning", "SMS danh thuc qua cu, bo qua")
                continue
            expected = hmac.new(
                key, str(ts).encode("ascii"), hashlib.sha256
            ).hexdigest()[:16]
            if not hmac.compare_digest(parts[2].lower(), expected):
                self.diagnostics.log("warning", "SMS danh thuc sai HMAC, bo qua")
                continue
            if ts <= self._wake_last_ts:
                self.diagnostics.log("warning", "SMS danh thuc replay, bo qua")
                continue
            self._wake_last_ts = ts
            if self._wake_ts_path is not None:
                try:
                    self._wake_ts_path.write_text(str(ts), encoding="utf-8")
                except OSError as exc:
                    self.diagnostics.log(
                        "warning", f"khong luu duoc moc SMS: {exc}"
                    )
            self.wake_sms_ok = True
            self.diagnostics.log("info", "SMS danh thuc hop le")
            return
        if messages:
            self.diagnostics.log("info", f"doc {len(messages)} SMS, khong co token hop le")

    def _on_power_sleep(self) -> None:
        """SoC chuẩn bị ngủ: đồng bộ hàng đợi rồi bảo MCU cắt rail.

        Không có lệnh riêng cho "SoC xin ngủ"; hợp đồng dùng
        `CMD = SOC_SHUTDOWN_DONE` (docs/03 §5, docs/15 §2.5). Firmware hiện tại
        chỉ cắt rail khi MCU đang ở trạng thái SHUTDOWN, nên hành vi cắt rail
        sau clip là CHƯA XÁC MINH trên board thật; app vẫn phải báo.
        """
        if self.sleep_requested:
            return
        thread = self._upload_thread
        if thread is not None and thread.is_alive():
            self.diagnostics.log(
                "warning", "dang tai clip; cho toi da 5 s truoc khi ngu"
            )
            thread.join(timeout=5.0)
            self._collect_upload()
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
        self._try_upload(now)

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
            "ota.start": self._cmd_ota_start,
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
        if self.spool is None:
            raise CommandError("NOT_IMPLEMENTED", "chua cau hinh tai clip len kho")
        clip_id = str(params["clip_id"])
        for item in self.spool.pending_ids():
            if item == clip_id:
                return {"clip_id": clip_id, "state": "queued"}
        clip = self.recorder.clip(clip_id)
        if clip is None:
            raise CommandError("BAD_ARGS", f"khong co clip {clip_id}")
        try:
            self.spool.add(clip.clip_id, clip.path, clip.size_b)
        except UploadError as exc:
            raise CommandError("INTERNAL", str(exc)) from exc
        return {"clip_id": clip_id, "state": "queued"}

    def _cmd_ota_start(self, params: dict) -> dict:
        if self.ota is None:
            raise CommandError(
                "NOT_IMPLEMENTED",
                "chua cau hinh bo xac minh chu ky; tu choi cap nhat",
            )
        manifest = {
            "version": params.get("version"),
            "url": params.get("url"),
            "sha256": params.get("sha256"),
            "size": params.get("size"),
            "signature": params.get("signature", ""),
        }
        try:
            status = self.ota.stage(manifest)
        except OtaError as exc:
            raise CommandError("BAD_ARGS", str(exc)) from exc
        self.diagnostics.log(
            "info", f"OTA staged version={status.version} state={status.state}"
        )
        return {"state": status.state, "version": status.version}

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
