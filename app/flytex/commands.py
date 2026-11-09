"""Xử lý lệnh từ cloud và tạo ack.

Envelope theo `mqtt_gen.ENVELOPE_FIELDS`, phiên bản `mqtt_gen.VERSION`, `dev`
phải khớp thiết bị. Mỗi lệnh trong `mqtt_gen.COMMANDS` được kiểm tra tham số
bắt buộc, kiểu và enum. `ota.start` luôn trả `NOT_IMPLEMENTED` — không giả vờ
thành công.

Ack có cùng `id` với lệnh, gửi lên topic `dev/{dev}/ack`, chứa `ok`,
`error` (null khi thành công) và `result` nếu handler trả dict.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping

from . import mqtt_gen
from .clock import Clock
from .config import ALLOWED_KEYS, ConfigError, validate_schedule

__all__ = ["CommandError", "CommandRouter", "Handler"]

Handler = Callable[[dict], "dict | None"]
LogFn = Callable[[str, str], None]

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_ENVELOPE_NAMES = {name for name, _required in mqtt_gen.ENVELOPE_FIELDS}


class CommandError(Exception):
    """Handler từ chối lệnh với mã lỗi trong `mqtt_gen.ACK_ERRORS`."""

    def __init__(self, code: str, message: str = "") -> None:
        if code not in mqtt_gen.ACK_ERRORS:
            raise ValueError(f"ack error code khong hop le: {code!r}")
        self.code = code
        self.message = message
        text = code if not message else f"{code}: {message}"
        super().__init__(text)


#: Ràng buộc bổ sung không có trong file sinh (nguồn: spec/mqtt.toml).
_EXTRA_RULES: dict[str, dict[str, dict[str, object]]] = {
    "live.start": {"duration_s": {"min": 10, "max": 600}},
    "mode.set": {"mode": {"enum": ("eco", "watch")}},
    "config.set": {"key": {"enum": ALLOWED_KEYS}},
    "schedule.set": {},
}


class CommandRouter:
    """Kiểm tra envelope/tham số rồi gọi handler."""

    def __init__(
        self,
        handlers: Mapping[str, Handler],
        dev: str | None = None,
        clock: Clock | None = None,
        log: LogFn | None = None,
    ) -> None:
        self._handlers: dict[str, Handler] = dict(handlers)
        self._dev = dev
        self._clock = clock
        self._log = log

    # -- đăng ký -------------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self._handlers

    def register(self, name: str, handler: Handler) -> None:
        if name in self._handlers:
            raise ValueError(f"handler da ton tai: {name}")
        if name not in mqtt_gen.COMMANDS:
            raise ValueError(f"lenh khong ton tai: {name}")
        self._handlers[name] = handler

    @property
    def handlers(self) -> dict[str, Handler]:
        return dict(self._handlers)

    # -- xử lý ---------------------------------------------------------
    def dispatch(self, payload: bytes) -> tuple[str, bytes] | None:
        """Trả `(topic_ack, payload_ack)` hoặc `None` nếu không phải lệnh."""
        if isinstance(payload, (bytes, bytearray)):
            try:
                text = bytes(payload).decode("utf-8")
            except UnicodeDecodeError:
                return None
        elif isinstance(payload, str):
            text = payload
        else:
            return None
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        cmd_type = obj.get("type")
        if not isinstance(cmd_type, str):
            return None
        cmd_id = obj.get("id")
        if not isinstance(cmd_id, str) or not cmd_id:
            # Không có id thì không thể tạo ack đúng hợp đồng.
            return None
        dev = obj.get("dev")
        ack_dev = self._dev if self._dev is not None else (
            dev if isinstance(dev, str) else ""
        )
        if not _HEX16.match(cmd_id):
            return self._error(cmd_id, ack_dev, "BAD_ID", "id khong phai 16 hex")
        envelope_error = self._check_envelope(obj)
        if envelope_error is not None:
            return self._error(cmd_id, ack_dev, "BAD_ARGS", envelope_error)
        if cmd_type not in mqtt_gen.COMMANDS:
            return self._error(cmd_id, ack_dev, "BAD_ARGS", f"lenh la: {cmd_type}")
        if cmd_type == "ota.start" and cmd_type not in self._handlers:
            self._log_line("warning", f"lenh {cmd_type} bi tu choi: NOT_IMPLEMENTED")
            return self._error(
                cmd_id,
                ack_dev,
                "NOT_IMPLEMENTED",
                "OTA chua hien thuc (can chu ky va A/B)",
            )
        try:
            params = self._validate_params(cmd_type, obj)
        except CommandError as exc:
            return self._error(cmd_id, ack_dev, exc.code, exc.message)
        handler = self._handlers.get(cmd_type)
        if handler is None:
            self._log_line("error", f"khong co handler cho lenh {cmd_type}")
            return self._error(
                cmd_id, ack_dev, "INTERNAL", f"chua dang ky handler {cmd_type}"
            )
        try:
            result = handler(params)
        except CommandError as exc:
            self._log_line("warning", f"lenh {cmd_type} tu choi: {exc}")
            return self._error(cmd_id, ack_dev, exc.code, exc.message)
        except ConfigError as exc:
            self._log_line("warning", f"lenh {cmd_type} sai cau hinh: {exc}")
            return self._error(cmd_id, ack_dev, "BAD_ARGS", str(exc))
        except Exception as exc:  # noqa: BLE001 - biên giới tin cậy của router
            code = getattr(exc, "ack_code", None)
            self._log_line(
                "error", f"handler {cmd_type} nem {type(exc).__name__}: {exc}"
            )
            if isinstance(code, str) and code in mqtt_gen.ACK_ERRORS:
                return self._error(cmd_id, ack_dev, code, str(exc))
            return self._error(
                cmd_id, ack_dev, "INTERNAL", f"{type(exc).__name__}: {exc}"
            )
        if result is not None and not isinstance(result, dict):
            self._log_line(
                "error", f"handler {cmd_type} tra {type(result).__name__}, can dict"
            )
            return self._error(
                cmd_id, ack_dev, "INTERNAL", "handler phai tra dict hoac None"
            )
        return self._ack(cmd_id, ack_dev, ok=True, error=None, result=result)

    # -- kiểm tra ------------------------------------------------------
    def _check_envelope(self, obj: dict) -> str | None:
        for name, required in mqtt_gen.ENVELOPE_FIELDS:
            if required and name not in obj:
                return f"thieu truong envelope: {name}"
        version = obj.get("v")
        if isinstance(version, bool) or not isinstance(version, int):
            return "v phai la so nguyen"
        if version != mqtt_gen.VERSION:
            return f"v khong ho tro: {version}"
        dev = obj.get("dev")
        if not isinstance(dev, str):
            return "dev phai la chuoi"
        if self._dev is not None and dev != self._dev:
            return "dev khong khop thiet bi"
        timestamp = obj.get("ts")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            return "ts phai la so nguyen"
        return None

    def _validate_params(self, cmd_type: str, obj: dict) -> dict:
        params: dict[str, object] = {}
        spec = mqtt_gen.COMMANDS[cmd_type]
        for name, rule in spec.items():
            if name in obj:
                value = obj[name]
                self._check_type(name, value, str(rule["type"]))
                params[name] = value
            elif rule["required"]:
                raise CommandError("BAD_ARGS", f"thieu tham so bat buoc: {name}")
        for name, constraints in _EXTRA_RULES.get(cmd_type, {}).items():
            if name not in params:
                continue
            value = params[name]
            allowed = constraints.get("enum")
            if isinstance(allowed, (list, tuple, set)) and value not in allowed:
                raise CommandError(
                    "BAD_ARGS",
                    f"{name} khong hop le: {value!r}; cho phep: "
                    + ", ".join(str(item) for item in allowed),
                )
            minimum = constraints.get("min")
            if isinstance(minimum, int) and isinstance(value, int) and value < minimum:
                raise CommandError("BAD_ARGS", f"{name} nho hon {minimum}")
            maximum = constraints.get("max")
            if isinstance(maximum, int) and isinstance(value, int) and value > maximum:
                raise CommandError("BAD_ARGS", f"{name} lon hon {maximum}")
        if cmd_type == "schedule.set" and "entries" in params:
            try:
                params["entries"] = validate_schedule(params["entries"])
            except ConfigError as exc:
                raise CommandError("BAD_ARGS", str(exc)) from exc
        return params

    @staticmethod
    def _check_type(name: str, value: object, expected: str) -> None:
        if expected == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise CommandError("BAD_ARGS", f"{name} phai la so nguyen")
        elif expected == "string":
            if not isinstance(value, str):
                raise CommandError("BAD_ARGS", f"{name} phai la chuoi")
        elif expected == "array":
            if not isinstance(value, list):
                raise CommandError("BAD_ARGS", f"{name} phai la mang")
        else:  # pragma: no cover - mqtt_gen chỉ sinh ba kiểu này
            raise CommandError("BAD_ARGS", f"kieu tham so khong ho tro: {expected}")

    # -- ack -----------------------------------------------------------
    def _ack(
        self,
        cmd_id: str,
        dev: str,
        *,
        ok: bool,
        error: str | None,
        result: dict | None = None,
    ) -> tuple[str, bytes]:
        timestamp = int(self._clock.now() if self._clock is not None else 0)
        ack: dict[str, object] = {
            "v": mqtt_gen.VERSION,
            "id": cmd_id,
            "dev": dev,
            "ts": timestamp,
            "type": "ack",
            "ok": bool(ok),
            "error": error,
        }
        if result is not None:
            ack["result"] = result
        body = json.dumps(ack, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        return mqtt_gen.ack_topic(dev), body

    def _error(
        self, cmd_id: str, dev: str, code: str, detail: str
    ) -> tuple[str, bytes]:
        self._log_line("warning", f"ack loi {code}: {detail}")
        return self._ack(cmd_id, dev, ok=False, error=code)

    def _log_line(self, level: str, message: str) -> None:
        if self._log is not None:
            self._log(level, message)
