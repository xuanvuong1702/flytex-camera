"""Nạp firmware MCU đã biên dịch thành thư viện và bọc bằng ctypes.

Firmware C là nguồn sự thật cho hành vi regmap và máy trạng thái nguồn; mô phỏng
không viết lại logic đó bằng Python.
"""

from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Cùng giá trị với enum trong firmware/mcu/include/flytex/hal.h
PIN_PIR = 0
PIN_VBUS = 1
PIN_MODEM_STATUS = 2
PIN_SOC_READY = 3
PIN_MODEM_RI = 4
PIN_SOC_PWR = 8
PIN_MODEM_PWR = 9
PIN_IRQ = 10
PIN_IR_LED = 11
PIN_CHG_INHIBIT = 12

ADC_VBAT = 0
TEMP_BATT = 0
TEMP_AMB = 1
TEMP_ABSENT = -128


class FirmwareMissing(RuntimeError):
    pass


def library_candidates() -> list[Path]:
    build = ROOT / "firmware" / "mcu" / "build"
    names = [
        "flytexmcu.dll",
        "libflytexmcu.so",
        "flytexmcu.so",
        "libflytexmcu.dylib",
        "flytexmcu.dylib",
    ]
    return [build / name for name in names]


class McuSim:
    """Một instance firmware MCU trong bộ nhớ tiến trình."""

    def __init__(self, lib_path: Path | None = None) -> None:
        path = lib_path or next((p for p in library_candidates() if p.exists()), None)
        if path is None:
            raise FirmwareMissing(
                "chưa có thư viện firmware. Chạy: "
                "python firmware/mcu/tests/build.py lib"
            )
        self.library_path = Path(path)
        lib = ctypes.CDLL(str(self.library_path))
        lib.fsim_new.restype = ctypes.c_void_p
        lib.fsim_new.argtypes = []
        lib.fsim_free.restype = None
        lib.fsim_free.argtypes = [ctypes.c_void_p]
        lib.fsim_set_input.restype = ctypes.c_int
        lib.fsim_set_input.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.fsim_set_adc_mv.restype = ctypes.c_int
        lib.fsim_set_adc_mv.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint]
        lib.fsim_set_temp_c.restype = ctypes.c_int
        lib.fsim_set_temp_c.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.fsim_step.restype = None
        lib.fsim_step.argtypes = [ctypes.c_void_p]
        lib.fsim_advance_ms.restype = ctypes.c_int
        lib.fsim_advance_ms.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        lib.fsim_i2c_read.restype = ctypes.c_int
        lib.fsim_i2c_read.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        lib.fsim_i2c_write.restype = ctypes.c_int
        lib.fsim_i2c_write.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        lib.fsim_get_output.restype = ctypes.c_int
        lib.fsim_get_output.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.fsim_stats_json.restype = ctypes.c_char_p
        lib.fsim_stats_json.argtypes = [ctypes.c_void_p]
        lib.fsim_now_ms.restype = ctypes.c_uint
        lib.fsim_now_ms.argtypes = [ctypes.c_void_p]
        self.lib = lib
        self.handle = lib.fsim_new()
        if not self.handle:
            raise FirmwareMissing("fsim_new trả NULL")

    # -- đầu vào --------------------------------------------------------
    def set_input(self, pin: int, level: int) -> None:
        rc = self.lib.fsim_set_input(self.handle, pin, level)
        if rc != 0:
            raise ValueError(f"fsim_set_input(pin={pin}) trả {rc}")

    def set_adc_mv(self, channel: int, mv: int) -> None:
        rc = self.lib.fsim_set_adc_mv(self.handle, channel, mv)
        if rc != 0:
            raise ValueError(f"fsim_set_adc_mv(ch={channel}) trả {rc}")

    def set_temp_c(self, sensor: int, celsius: int) -> None:
        rc = self.lib.fsim_set_temp_c(self.handle, sensor, celsius)
        if rc != 0:
            raise ValueError(f"fsim_set_temp_c(sensor={sensor}) trả {rc}")

    # -- thời gian ------------------------------------------------------
    def step(self) -> None:
        self.lib.fsim_step(self.handle)

    def advance_ms(self, ms: int) -> int:
        return int(self.lib.fsim_advance_ms(self.handle, ms))

    def now_ms(self) -> int:
        return int(self.lib.fsim_now_ms(self.handle))

    # -- bus ------------------------------------------------------------
    def i2c_read(self, reg: int, length: int) -> bytes:
        if length <= 0:
            return b""
        buffer = (ctypes.c_ubyte * length)()
        rc = self.lib.fsim_i2c_read(self.handle, reg, buffer, length)
        if rc != 0:
            raise OSError(f"I2C NACK đọc 0x{reg:02X} ({length} byte), mã {rc}")
        return bytes(buffer)

    def i2c_write(self, reg: int, data: bytes) -> None:
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        rc = self.lib.fsim_i2c_write(self.handle, reg, buffer, len(data))
        if rc != 0:
            raise OSError(f"I2C NACK ghi 0x{reg:02X}, mã {rc}")

    # -- đầu ra ---------------------------------------------------------
    def get_output(self, pin: int) -> int:
        value = int(self.lib.fsim_get_output(self.handle, pin))
        if value < 0:
            raise ValueError(f"pin {pin} không phải output")
        return value

    def stats(self) -> dict:
        raw = self.lib.fsim_stats_json(self.handle)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def close(self) -> None:
        if self.handle:
            self.lib.fsim_free(self.handle)
            self.handle = None

    def __enter__(self) -> "McuSim":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 - không ném trong __del__
            pass


if __name__ == "__main__":
    sim = McuSim()
    try:
        proto = sim.i2c_read(0x00, 1)[0]
        print(f"PROTO_VER=0x{proto:02X} stats={sim.stats()}")
    finally:
        sim.close()
        print(f"lib={sim.library_path}", file=sys.stderr)
