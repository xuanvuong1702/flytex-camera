"""Test router lệnh MQTT, cấu hình và định danh."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from _helpers import FakeClock
except ImportError:  # pragma: no cover
    from app.tests._helpers import FakeClock

from flytex import mqtt_gen
from flytex.commands import CommandError, CommandRouter
from flytex.config import Config, ConfigError
from flytex.identity import Identity, IdentityError

DEV = "abc123def456"
CMD_ID = "0123456789abcdef"


def command(cmd: str, args: dict | None = None, **overrides) -> bytes:
    """Lệnh dạng phẳng: `type` là tên lệnh, tham số ở mức ngoài cùng.

    Đây là hợp đồng hiện hành (spec/mqtt.toml, docs/15 §5.2): không có trường
    `cmd`/`args` lồng nhau.
    """
    payload = {
        "v": mqtt_gen.VERSION,
        "id": CMD_ID,
        "dev": DEV,
        "ts": 1_700_000_000,
        "type": cmd,
    }
    payload.update(args or {})
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


def ack_of(result: tuple[str, bytes] | None) -> tuple[str, dict]:
    assert result is not None
    topic, payload = result
    return topic, json.loads(payload.decode("utf-8"))


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[dict] = []

        def status_handler(args: dict) -> dict:
            self.calls.append(args)
            return {"ok": 1}

        self.router = CommandRouter(
            {"status.get": status_handler, "mode.set": lambda args: {"mode": args["mode"]}},
            dev=DEV,
            clock=FakeClock(),
        )

    def test_valid_command_acks(self) -> None:
        topic, ack = ack_of(self.router.dispatch(command("status.get")))
        self.assertEqual(topic, mqtt_gen.ack_topic(DEV))
        self.assertEqual(ack["id"], CMD_ID)
        self.assertTrue(ack["ok"])
        self.assertIsNone(ack["error"])
        self.assertEqual(ack["result"], {"ok": 1})
        self.assertEqual(self.calls, [{}])

    def test_ack_matches_schema(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("status.get")))
        for field in ("ok", "error"):
            self.assertIn(field, ack)
        self.assertEqual(ack["type"], "ack")

    def test_nested_cmd_envelope_rejected(self) -> None:
        # Hợp đồng là dạng phẳng; bản tin kiểu {type:"cmd", cmd:"..."} bị từ chối rõ ràng.
        payload = json.dumps(
            {
                "v": 1,
                "id": CMD_ID,
                "dev": DEV,
                "ts": 0,
                "type": "cmd",
                "cmd": "status.get",
                "args": {},
            }
        ).encode()
        _, ack = ack_of(self.router.dispatch(payload))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_unknown_command_rejected(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("do.magic")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_ota_is_not_implemented(self) -> None:
        _, ack = ack_of(
            self.router.dispatch(
                command("ota.start", {"url": "https://x/y", "sha256": "a" * 64, "version": "1.2"})
            )
        )
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "NOT_IMPLEMENTED")

    def test_missing_required_arg(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("mode.set", {})))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_bad_enum_arg(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("mode.set", {"mode": "sleepy"})))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_wrong_version_rejected(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("status.get", v=99)))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_wrong_device_rejected(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("status.get", dev="zzz999yyy888")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_bad_id_rejected(self) -> None:
        _, ack = ack_of(self.router.dispatch(command("status.get", id="ABC")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ID")

    def test_non_command_payload_ignored(self) -> None:
        # Bản tin không phải lệnh nhưng vẫn có id hợp lệ: trả lỗi rõ, không im lặng.
        payload = json.dumps({"v": 1, "id": CMD_ID, "dev": DEV, "ts": 0, "type": "evt"}).encode()
        _, ack = ack_of(self.router.dispatch(payload))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BAD_ARGS")

    def test_invalid_json_ignored(self) -> None:
        self.assertIsNone(self.router.dispatch(b"{not json"))

    def test_handler_error_becomes_internal(self) -> None:
        router = CommandRouter({"status.get": lambda args: 1 / 0}, dev=DEV)
        _, ack = ack_of(router.dispatch(command("status.get")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "INTERNAL")

    def test_handler_command_error_is_reported(self) -> None:
        def handler(args: dict) -> dict:
            raise CommandError("BUSY", "dang ghi")

        router = CommandRouter({"status.get": handler}, dev=DEV)
        _, ack = ack_of(router.dispatch(command("status.get")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "BUSY")

    def test_unregistered_handler_is_internal(self) -> None:
        router = CommandRouter({}, dev=DEV)
        _, ack = ack_of(router.dispatch(command("status.get")))
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["error"], "INTERNAL")

    def test_registering_unknown_command_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.router.register("do.magic", lambda args: {})

    def test_duplicate_registration_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.router.register("status.get", lambda args: {})


class ConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self) -> None:
        config = Config()
        self.assertEqual(config.mode, "eco")
        self.assertEqual(config.mqtt_port, 8883)
        self.assertEqual(config.schedule, [])

    def test_bad_mode_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            Config(mode="sleepy")

    def test_port_out_of_range_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            Config(mqtt_port=70000)

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(mode="watch", clip_s=20, apn="internet")
            config.save(path)
            loaded = Config.load(path)
            self.assertEqual(loaded.to_dict(), config.to_dict())

    def test_load_missing_file_raises(self) -> None:
        with self.assertRaises(ConfigError):
            Config.load("khong-ton-tai.json")

    def test_set_allowed_valid_key(self) -> None:
        config = Config()
        config.set_allowed("clip_s", 45)
        self.assertEqual(config.clip_s, 45)

    def test_set_allowed_rejects_unknown_key(self) -> None:
        config = Config()
        with self.assertRaises(ConfigError):
            config.set_allowed("khong_co", 1)

    def test_schedule_limit(self) -> None:
        entry = {"start": "00:00", "end": "01:00", "days": [1], "enabled": True}
        with self.assertRaises(ConfigError):
            Config(schedule=[entry] * 9)

    def test_schedule_bad_time_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            Config(schedule=[{"start": "25:00", "end": "26:00", "days": [1], "enabled": True}])


class IdentityTests(unittest.TestCase):
    def test_generate_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            identity = Identity.generate_for_test(tmp)
            loaded = Identity.load(tmp)
            self.assertEqual(loaded.device_id, identity.device_id)
            self.assertEqual(len(identity.cert_paths), 3)

    def test_missing_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(IdentityError):
                Identity.load(Path(tmp) / "khong-co")


if __name__ == "__main__":
    unittest.main(verbosity=2)
