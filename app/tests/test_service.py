"""Test tích hợp mức dịch vụ: boot, PIR, lệnh MQTT, đi ngủ."""

from __future__ import annotations

import json
import random
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock, make_mcu
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock, make_mcu

from flytex import mqtt_gen
from flytex.cloud import MemoryBus
from flytex.commands import CommandRouter
from flytex.config import Config, ConfigError
from flytex.diagnostics import Diagnostics
from flytex.identity import Identity
from flytex.media import FakeSource
from flytex.modem import AtClient, FakeModem, SmsMessage
from flytex.recorder import SegmentRecorder
from flytex.service import DeviceService
from flytex.tsmux import TsMuxer
from flytex.uplink import UplinkQueue
from flytex.upload import FakeUploader, UploadResult, UploadSpool


class ServiceFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = FakeClock(start=1_700_000_000.0)
        self.mcu_client, self.memory, _ = make_mcu(self.clock)
        self.identity = Identity.generate_for_test(self.root / "identity")
        self.config = Config(
            clip_s=5,
            settle_s=1,
            live_s=10,
            apn="internet",
            mqtt_host="broker.test",
            relay_url="rtsp://relay.test/live",
            allow_raw_muxer=True,
        )
        with (self.root / "config.json").open("w", encoding="utf-8") as handle:
            json.dump(self.config.to_dict(), handle)
        fake_modem = FakeModem(self.clock)
        self.modem = AtClient(fake_modem, self.clock, pwrkey=fake_modem)
        self.media = FakeSource(self.clock, fps=5.0)
        self.recorder = SegmentRecorder(
            self.root / "clips", self.clock, TsMuxer(),
            segment_s=2.0, max_bytes=1 << 20, pin_budget_bytes=1 << 19,
        )
        self.queue = UplinkQueue(
            self.root / "queue.jsonl", self.clock,
            max_bytes=1 << 20, rng=random.Random(7),
        )
        self.uploader = FakeUploader()
        self.spool = UploadSpool(self.root / "upload.jsonl", self.clock)
        self.bus = MemoryBus()
        self.publisher = self.bus.publisher()
        self.router = CommandRouter({}, dev=self.identity.device_id, clock=self.clock)
        self.diagnostics = Diagnostics(self.root / "diag", self.clock)
        self.service = DeviceService(
            self.identity,
            self.config,
            self.clock,
            self.mcu_client,
            self.modem,
            self.media,
            self.recorder,
            self.queue,
            self.publisher,
            self.router,
            self.diagnostics,
            config_path=self.root / "config.json",
            uploader=self.uploader,
            spool=self.spool,
        )

    def tearDown(self) -> None:
        self.service.stop()
        self._tmp.cleanup()

    def _run(self, seconds: float, step: float = 0.5) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            self.clock.advance(step)
            self.service.step(self.clock.now())
            elapsed += step

    def _wait_upload_idle(self, timeout: float = 2.0) -> None:
        """Chờ luồng tải kết thúc và được thu gom (test có thread thật)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            thread = self.service._upload_thread
            if thread is None:
                return
            thread.join(0.05)
            self.service.step(self.clock.now())
            time.sleep(0.005)
        self.fail("luồng tải không kết thúc trong thời gian cho phép")

    def _publish_command(self, cmd: str, **params: object) -> str:
        message_id = f"{random.Random(len(cmd)).getrandbits(64):016x}"
        payload = {
            "v": mqtt_gen.VERSION,
            "id": message_id,
            "dev": self.identity.device_id,
            "ts": int(self.clock.now()),
            "type": cmd,
        }
        payload.update(params)
        self.bus.publish_message(
            mqtt_gen.cmd_topic(self.identity.device_id),
            json.dumps(payload).encode("utf-8"),
        )
        return message_id

    def _acks(self) -> list[dict]:
        acks = []
        for payload in self.bus.messages_of(mqtt_gen.ack_topic(self.identity.device_id)):
            acks.append(json.loads(payload.decode("utf-8")))
        return acks

    def _status(self) -> dict:
        raw = self.bus.retained(mqtt_gen.status_topic(self.identity.device_id))
        self.assertIsNotNone(raw, "phải có status retained")
        return json.loads(raw.decode("utf-8"))


class BootTests(ServiceFixture):
    def test_boot_publishes_status_and_boot(self) -> None:
        self.service.boot()
        self.assertTrue(self.service.booted)
        status = self._status()
        self.assertEqual(status["type"], "status")
        self.assertEqual(status["dev"], self.identity.device_id)
        self.assertIn(status["state"], {"s0", "s1"})
        self.assertEqual(status["proto"], "1.1")
        types = [json.loads(item)["type"] for item in self.bus.messages_of(mqtt_gen.event_topic(self.identity.device_id))]
        self.assertIn("boot", types)

    def test_boot_is_idempotent(self) -> None:
        self.service.boot()
        before = len(self.bus.messages_of(mqtt_gen.event_topic(self.identity.device_id)))
        self.service.boot()
        after = len(self.bus.messages_of(mqtt_gen.event_topic(self.identity.device_id)))
        self.assertEqual(before, after)


class RecordTests(ServiceFixture):
    def test_pir_records_clip_and_publishes_motion(self) -> None:
        self.service.boot()
        self.memory.raise_event("PIR")
        self._run(7.0)
        self.assertFalse(self.recorder.recording)
        types = [json.loads(item)["type"] for item in self.bus.messages_of(mqtt_gen.event_topic(self.identity.device_id))]
        self.assertIn("motion", types)
        self.assertGreaterEqual(len(self.recorder.list_clips()), 1)

    def test_sleep_is_requested_after_clip(self) -> None:
        self.service.boot()
        self.memory.raise_event("PIR")
        self._run(9.0)
        self.assertTrue(self.service.sleep_requested)
        self.assertIn("SOC_SHUTDOWN_DONE", self.memory.commands)


class CommandTests(ServiceFixture):
    def test_status_get_is_acked(self) -> None:
        self.service.boot()
        message_id = self._publish_command("status.get")
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertTrue(acks[0]["ok"])

    def test_ota_is_not_implemented(self) -> None:
        self.service.boot()
        message_id = self._publish_command(
            "ota.start", url="https://x/y", sha256="a" * 64, version="1.2"
        )
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertFalse(acks[0]["ok"])
        self.assertEqual(acks[0]["error"], "NOT_IMPLEMENTED")

    def test_mode_set_busy_while_recording(self) -> None:
        self.service.boot()
        self.memory.raise_event("PIR")
        self._run(1.0)
        message_id = self._publish_command("mode.set", mode="watch")
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertFalse(acks[0]["ok"])
        self.assertEqual(acks[0]["error"], "BUSY")

    def test_live_start_enters_live(self) -> None:
        self.service.boot()
        message_id = self._publish_command("live.start", duration_s=10)
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertTrue(acks[0]["ok"])
        self.assertIn("live_url", acks[0]["result"])
        self.assertEqual(self.service.power.state.value, "s3")

    def test_unknown_command_rejected(self) -> None:
        self.service.boot()
        message_id = self._publish_command("do.magic")
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertFalse(acks[0]["ok"])
        self.assertEqual(acks[0]["error"], "BAD_ARGS")


class _FakeOta:
    def __init__(self) -> None:
        self.manifests: list[dict] = []

    def stage(self, manifest: dict):
        self.manifests.append(manifest)

        class _Status:
            state = "staged"
            version = manifest["version"]

        return _Status()

    def check_boot(self, running_version: str):
        class _Status:
            state = "idle"

        return _Status()


class OtaCommandTests(ServiceFixture):
    def test_ota_stage_calls_manager(self) -> None:
        self.service.boot()
        fake = _FakeOta()
        self.service.ota = fake
        message_id = self._publish_command(
            "ota.start",
            url="https://example.com/1.2.0.img",
            sha256="a" * 64,
            version="1.2.0",
            size=1024,
            signature="sig",
        )
        self.service.step(self.clock.now())
        acks = [ack for ack in self._acks() if ack["id"] == message_id]
        self.assertTrue(acks)
        self.assertTrue(acks[0]["ok"])
        self.assertEqual(acks[0]["result"]["state"], "staged")
        self.assertEqual(fake.manifests[0]["version"], "1.2.0")


class UploadTests(ServiceFixture):
    def test_clip_is_uploaded_and_reported(self) -> None:
        self.service.boot()
        self.memory.raise_event("PIR")
        self._run(6.0)
        self._wait_upload_idle()
        self.assertEqual(len(self.uploader.calls), 1)
        types = [
            json.loads(item)["type"]
            for item in self.bus.messages_of(mqtt_gen.event_topic(self.identity.device_id))
        ]
        self.assertIn("clip_ready", types)
        self.assertEqual(len(self.spool), 0)

    def test_failed_upload_retries_later(self) -> None:
        self.service.boot()
        self.uploader.fail_times = 1
        self.memory.raise_event("PIR")
        self._run(6.0)
        self._wait_upload_idle()
        self.assertEqual(len(self.uploader.calls), 0)
        self.assertEqual(len(self.spool), 1)
        self.clock.advance(31.0)
        self._run(0.5)
        self._wait_upload_idle()
        self.assertEqual(len(self.uploader.calls), 1)
        self.assertEqual(len(self.spool), 0)


class _SlowUploader:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def upload(self, path, clip_id: str) -> UploadResult:
        self.started.set()
        self.release.wait(5.0)
        self.calls += 1
        return UploadResult(clip_id=clip_id, url="https://slow/x", size_b=1)


class AsyncUploadTests(ServiceFixture):
    def test_upload_runs_off_the_main_loop(self) -> None:
        self.service.boot()
        slow = _SlowUploader()
        self.service.uploader = slow
        self.memory.raise_event("PIR")
        self._run(5.5)
        self.assertTrue(slow.started.wait(2.0), "upload phải bắt đầu")
        start = time.monotonic()
        self.service.step(self.clock.now())
        self.assertLess(time.monotonic() - start, 0.5, "step không được chặn")
        slow.release.set()
        self._wait_upload_idle()
        self.assertEqual(slow.calls, 1)
        self.assertEqual(len(self.spool), 0)


class SmsWakeTests(ServiceFixture):
    SECRET = "00112233445566778899aabbccddeeff"

    def _sms(self, counter: int, sig: str | None = None) -> SmsMessage:
        import hashlib
        import hmac

        if sig is None:
            sig = hmac.new(
                bytes.fromhex(self.SECRET), str(counter).encode("ascii"), hashlib.sha256
            ).hexdigest()[:16]
        return SmsMessage(index=1, number="+8490", text=f"W {counter} {sig}")

    def _setup_sms(self) -> None:
        self.service.config.wake_chan = "sms"
        self.service.config.wake_secret = self.SECRET

    def test_valid_hmac_accepted(self) -> None:
        self._setup_sms()
        self.modem.sms_read = lambda index=None: [self._sms(1)]
        self.service._consume_wake_sms()
        self.assertTrue(self.service.wake_sms_ok)

    def test_wrong_hmac_rejected(self) -> None:
        self._setup_sms()
        self.modem.sms_read = lambda index=None: [self._sms(1, sig="0" * 16)]
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)

    def test_low_counter_rejected(self) -> None:
        self._setup_sms()
        self.service._wake_last_ts = 100
        self.modem.sms_read = lambda index=None: [self._sms(99)]
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)

    def test_replay_rejected(self) -> None:
        self._setup_sms()
        self.modem.sms_read = lambda index=None: [self._sms(1)]
        self.service._consume_wake_sms()
        self.assertTrue(self.service.wake_sms_ok)
        self.service.wake_sms_ok = False
        self._consume_same = True
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)

    def test_cold_boot_without_clock_accepted(self) -> None:
        self._setup_sms()
        self.service._wake_last_ts = 0
        self.modem.sms_read = lambda index=None: [self._sms(1)]
        self.service._consume_wake_sms()
        self.assertTrue(self.service.wake_sms_ok)

    def test_allowlist_rejects_other_number(self) -> None:
        self._setup_sms()
        self.service.config.wake_numbers = "+8491"
        self.modem.sms_read = lambda index=None: [self._sms(1)]
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)

    def test_allowlist_accepts_configured_number(self) -> None:
        self._setup_sms()
        self.service.config.wake_numbers = "+8490"
        self.modem.sms_read = lambda index=None: [self._sms(1)]
        self.service._consume_wake_sms()
        self.assertTrue(self.service.wake_sms_ok)

    def test_watermark_is_persisted(self) -> None:
        self._setup_sms()
        self.modem.sms_read = lambda index=None: [self._sms(7)]
        self.service._consume_wake_sms()
        path = self.service._wake_ts_path
        self.assertIsNotNone(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "7")

    def test_missing_secret_rejected(self) -> None:
        self.service.config.wake_chan = "sms"
        self.service.config.wake_secret = ""
        self.modem.sms_read = lambda index=None: [self._sms(0)]
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)

    def test_secret_not_settable_remotely(self) -> None:
        self._setup_sms()
        with self.assertRaises(ConfigError):
            self.service.config.set_allowed("wake_secret", "00" * 16)

    def test_secret_not_in_mqtt_payloads(self) -> None:
        self._setup_sms()
        self.service.boot()
        topic = mqtt_gen.event_topic(self.identity.device_id)
        payloads = b" ".join(self.bus.messages_of(topic)).decode("utf-8", "replace")
        self.assertNotIn(self.SECRET, payloads)

    def test_ignored_when_channel_is_not_sms(self) -> None:
        self.service.config.wake_chan = "off"
        self.modem.sms_read = lambda index=None: [self._sms(0)]
        self.service._consume_wake_sms()
        self.assertFalse(self.service.wake_sms_ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
