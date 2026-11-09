"""Cấu hình thiết bị: đọc/ghi nguyên tử và danh sách khóa cho phép.

File cấu hình nằm ở `/data/config.json` (docs/14 §5). Ghi bằng file tạm cùng
thư mục rồi `os.replace`, nên mất điện không để lại file cấu hình nửa vời.

`Config.set_allowed` chỉ chấp nhận các khóa trong `ALLOWED_KEYS`; `schedule`
không đổi qua đường này mà dùng lệnh `schedule.set` để kiểm tra cả danh sách.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "ALLOWED_KEYS",
    "Config",
    "ConfigError",
    "LOG_LEVELS",
    "MODES",
    "WAKE_CHANNELS",
    "validate_schedule",
]

MODES = ("eco", "watch")
WAKE_CHANNELS = ("off", "modem_tcp_poll", "sms", "edrx_mqtt")
LOG_LEVELS = ("debug", "info", "warning", "error")

_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
_URL_SCHEMES = ("http://", "https://", "rtmp://", "rtsp://")


class ConfigError(Exception):
    """Cấu hình không hợp lệ hoặc không đọc/ghi được."""


def _as_int(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{name} phai la so nguyen, khong phai bool")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[+-]?[0-9]+", text):
            raise ConfigError(f"{name} phai la so nguyen: {value!r}")
        number = int(text, 10)
    else:
        raise ConfigError(f"{name} phai la so nguyen: {value!r}")
    if not low <= number <= high:
        raise ConfigError(f"{name} ngoai dai {low}..{high}: {number}")
    return number


def _as_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
    raise ConfigError(f"{name} phai la bool: {value!r}")


def _as_enum(value: object, name: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} phai la chuoi: {value!r}")
    text = value.strip().lower()
    if text not in allowed:
        raise ConfigError(
            f"{name} khong hop le: {value!r}; cho phep: {', '.join(allowed)}"
        )
    return text


def _as_text(
    value: object,
    name: str,
    *,
    max_len: int,
    allow_empty: bool = True,
    schemeless: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} phai la chuoi: {value!r}")
    text = value.strip()
    if not allow_empty and not text:
        raise ConfigError(f"{name} khong duoc rong")
    if len(text) > max_len:
        raise ConfigError(f"{name} dai qua {max_len} ky tu")
    if any(ord(char) < 0x20 for char in text):
        raise ConfigError(f"{name} chua ky tu dieu khien")
    if any(char.isspace() for char in text):
        raise ConfigError(f"{name} khong duoc chua khoang trang")
    if schemeless and text and not text.startswith(_URL_SCHEMES):
        raise ConfigError(
            f"{name} phai bat dau bang mot trong: {', '.join(_URL_SCHEMES)}"
        )
    return text


def validate_schedule(entries: object) -> list[dict]:
    """Kiểm tra và chuẩn hóa lịch thức (tối đa 8 mục).

    Mỗi mục: ``{"start": "HH:MM", "end": "HH:MM", "days": [1..7],
    "enabled": bool}``. Ngày dùng ISO (1 = thứ Hai). Khung giờ qua nửa đêm
    (start > end) được phép.
    """
    if not isinstance(entries, list):
        raise ConfigError("schedule phai la danh sach")
    if len(entries) > 8:
        raise ConfigError("schedule toi da 8 muc")
    normalized: list[dict] = []
    required = {"start", "end", "days", "enabled"}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigError(f"schedule[{index}] phai la object")
        extra = set(entry) - required
        if extra:
            raise ConfigError(
                f"schedule[{index}] co khoa la: {', '.join(sorted(extra))}"
            )
        missing = required - set(entry)
        if missing:
            raise ConfigError(
                f"schedule[{index}] thieu khoa: {', '.join(sorted(missing))}"
            )
        start = entry["start"]
        end = entry["end"]
        for name, value in (("start", start), ("end", end)):
            if not isinstance(value, str) or not _TIME_RE.match(value):
                raise ConfigError(
                    f"schedule[{index}].{name} phai dang HH:MM: {value!r}"
                )
        days = entry["days"]
        if not isinstance(days, list) or not days:
            raise ConfigError(f"schedule[{index}].days phai la danh sach khac rong")
        clean_days: list[int] = []
        for day in days:
            if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 7:
                raise ConfigError(f"schedule[{index}].days phai la 1..7")
            if day in clean_days:
                raise ConfigError(f"schedule[{index}].days bi trung: {day}")
            clean_days.append(day)
        enabled = entry["enabled"]
        if not isinstance(enabled, bool):
            raise ConfigError(f"schedule[{index}].enabled phai la bool")
        normalized.append(
            {
                "start": start,
                "end": end,
                "days": sorted(clean_days),
                "enabled": enabled,
            }
        )
    return normalized


def _validate_apn(value: object) -> str:
    text = _as_text(value, "apn", max_len=64)
    if text and any(ord(char) < 0x20 or ord(char) > 0x7E for char in text):
        raise ConfigError("apn phai la ASCII in duoc")
    return text


def _validate_port(value: object) -> int:
    return _as_int(value, "mqtt_port", 1, 65535)


def _validate_relay(value: object) -> str:
    return _as_text(value, "relay_url", max_len=512, schemeless=True)


def _validate_timezone(value: object) -> str:
    text = _as_text(value, "timezone", max_len=64, allow_empty=False)
    if "/" in text:
        area, _, city = text.partition("/")
        if not area or not city:
            raise ConfigError(f"timezone khong hop le: {value!r}")
    return text


_VALIDATORS = {
    "mode": lambda value: _as_enum(value, "mode", MODES),
    "clip_s": lambda value: _as_int(value, "clip_s", 5, 600),
    "live_s": lambda value: _as_int(value, "live_s", 10, 600),
    "settle_s": lambda value: _as_int(value, "settle_s", 0, 120),
    "apn": _validate_apn,
    "mqtt_host": lambda value: _as_text(value, "mqtt_host", max_len=255),
    "mqtt_port": _validate_port,
    "relay_url": _validate_relay,
    "wake_chan": lambda value: _as_enum(value, "wake_chan", WAKE_CHANNELS),
    "wake_period_s": lambda value: _as_int(value, "wake_period_s", 0, 86400),
    "wake_token": lambda value: _as_text(value, "wake_token", max_len=64),
    "wake_secret": lambda value: _as_text(value, "wake_secret", max_len=64),
    "allow_raw_muxer": lambda value: _as_bool(value, "allow_raw_muxer"),
    "log_level": lambda value: _as_enum(value, "log_level", LOG_LEVELS),
    "timezone": _validate_timezone,
}

#: Các khóa được đổi qua `config.set`. `schedule` dùng lệnh riêng.
ALLOWED_KEYS: tuple[str, ...] = tuple(_VALIDATORS)

FIELD_NAMES: tuple[str, ...] = tuple(_VALIDATORS) + ("schedule",)


@dataclass
class Config:
    """Cấu hình thiết bị với giá trị mặc định theo docs/04 §3.2."""

    mode: str = "eco"
    clip_s: int = 30
    live_s: int = 120
    settle_s: int = 10
    apn: str = ""
    mqtt_host: str = ""
    mqtt_port: int = 8883
    relay_url: str = ""
    wake_chan: str = "off"
    wake_period_s: int = 0
    wake_token: str = ""
    wake_secret: str = ""
    allow_raw_muxer: bool = True
    log_level: str = "info"
    schedule: list[dict] = field(default_factory=list)
    timezone: str = "Asia/Ho_Chi_Minh"

    def __post_init__(self) -> None:
        for name, validate in _VALIDATORS.items():
            setattr(self, name, validate(getattr(self, name)))
        self.schedule = validate_schedule(self.schedule)

    # -- chuyển đổi ----------------------------------------------------
    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "clip_s": self.clip_s,
            "live_s": self.live_s,
            "settle_s": self.settle_s,
            "apn": self.apn,
            "mqtt_host": self.mqtt_host,
            "mqtt_port": self.mqtt_port,
            "relay_url": self.relay_url,
            "wake_chan": self.wake_chan,
            "wake_period_s": self.wake_period_s,
            "wake_token": self.wake_token,
            "wake_secret": self.wake_secret,
            "allow_raw_muxer": self.allow_raw_muxer,
            "log_level": self.log_level,
            "schedule": [dict(entry) for entry in self.schedule],
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, data: object) -> "Config":
        if not isinstance(data, dict):
            raise ConfigError("config phai la object JSON")
        values: dict[str, object] = {}
        for name in FIELD_NAMES:
            if name in data:
                values[name] = data[name]
        return cls(**values)  # type: ignore[arg-type]

    # -- đọc/ghi -------------------------------------------------------
    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "Config":
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ConfigError(f"khong thay file cau hinh: {file_path}") from exc
        except OSError as exc:
            raise ConfigError(f"khong doc duoc cau hinh {file_path}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"cau hinh khong phai JSON hop le: {exc}") from exc
        try:
            return cls.from_dict(data)
        except ConfigError:
            raise
        except TypeError as exc:
            raise ConfigError(f"cau hinh sai kieu: {exc}") from exc

    def save(self, path: str | os.PathLike[str]) -> None:
        file_path = Path(path)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            body = json.dumps(
                self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
            )
            body += "\n"
            fd, temp_name = tempfile.mkstemp(
                prefix=file_path.name + ".",
                suffix=".tmp",
                dir=str(file_path.parent),
            )
        except OSError as exc:
            raise ConfigError(f"khong tao duoc file tam: {exc}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, file_path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise ConfigError(f"khong ghi duoc cau hinh {file_path}: {exc}") from exc

    # -- thay đổi có kiểm soát ----------------------------------------
    def set_allowed(self, key: str, value: object) -> object:
        """Đổi một khóa trong danh sách cho phép, trả giá trị đã chuẩn hóa."""
        if key not in ALLOWED_KEYS:
            raise ConfigError(
                "khoa khong duoc phep: "
                f"{key!r}; cho phep: {', '.join(ALLOWED_KEYS)}"
            )
        converted = _VALIDATORS[key](value)
        setattr(self, key, converted)
        return converted
