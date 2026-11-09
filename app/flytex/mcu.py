"""Giao tiếp MCU giám sát qua I2C.

Quy tắc thanh ghi lấy từ `spec/generated/regmap.md` (sinh từ
`spec/registers.toml`):

- thanh ghi nhiều byte là big-endian, byte cao ở địa chỉ thấp;
- đọc byte cao của nhóm `latch_read` chốt cả nhóm;
- ghi nhóm `commit_write` chỉ có hiệu lực khi ghi byte cuối;
- `EVENT` xóa khi đọc;
- ghi thanh ghi chỉ đọc, đọc thanh ghi chỉ ghi, hoặc địa chỉ không định nghĩa:
  NACK (`McuNack`).

`MemoryMcu` là mô phỏng độc lập với firmware C, dùng cho test và sim.
`I2cLink` là lớp mỏng cho `/dev/i2c-N` thật; chưa kiểm chứng trên phần cứng.
"""

from __future__ import annotations

import os
import sys
from typing import Protocol

from . import regs_gen
from .clock import Clock, RealClock


class McuError(Exception):
    """Lỗi giao tiếp MCU nói chung."""


class McuNack(McuError):
    """MCU NACK: truy cập thanh ghi không hợp lệ."""


class ProtocolMismatch(McuError):
    """Phiên bản giao thức MCU khác major mà ứng dụng yêu cầu."""


class McuLink(Protocol):
    """Bus MCU ở mức byte."""

    def read(self, addr: int, n: int = 1) -> bytes:
        """Đọc `n` byte từ địa chỉ `addr`."""

    def write(self, addr: int, data: bytes) -> None:
        """Ghi `data` bắt đầu từ địa chỉ `addr`."""

    def irq_wait(self, timeout: float) -> bool:
        """Chờ sự kiện; `True` nếu có sự kiện trong `timeout` giây."""

    def close(self) -> None:
        """Đóng bus."""


def _format_version(raw: int) -> str:
    return f"{raw >> 4}.{raw & 0x0F}"


def _check_uint(value: int, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} phai la so nguyen")
    if not low <= value <= high:
        raise ValueError(f"{name} ngoai dai {low}..{high}: {value}")
    return value


class McuClient:
    """Đọc/ghi regmap theo tên thanh ghi, không lộ địa chỉ cho tầng trên."""

    def __init__(self, link: McuLink) -> None:
        self._link = link
        self._proto_raw: int | None = None

    # -- thanh ghi thô -------------------------------------------------
    def _read(self, name: str, n: int | None = None) -> bytes:
        reg = regs_gen.REG_BY_NAME[name]
        count = reg.size if n is None else n
        return self._link.read(reg.addr, count)

    def _write(self, name: str, data: bytes) -> None:
        reg = regs_gen.REG_BY_NAME[name]
        if len(data) != reg.size:
            raise ValueError(f"{name} can {reg.size} byte, nhan {len(data)}")
        self._link.write(reg.addr, data)

    # -- phiên bản -----------------------------------------------------
    def check_protocol(self) -> None:
        """Đọc `PROTO_VER`; khác major thì từ chối làm việc."""
        raw = self._read("PROTO_VER")[0]
        self._proto_raw = raw
        major = raw >> 4
        if major != regs_gen.PROTO_MAJOR:
            raise ProtocolMismatch(
                f"MCU protocol {_format_version(raw)}, app requires major "
                f"{regs_gen.PROTO_MAJOR}"
            )

    def _proto_value(self) -> int:
        if self._proto_raw is None:
            self._proto_raw = self._read("PROTO_VER")[0]
        return self._proto_raw

    @property
    def proto_version(self) -> str:
        return _format_version(self._proto_value())

    @property
    def proto_major(self) -> int:
        return self._proto_value() >> 4

    @property
    def proto_minor(self) -> int:
        return self._proto_value() & 0x0F

    @property
    def fw_version(self) -> str:
        return _format_version(self._read("FW_VER")[0])

    # -- trạng thái, sự kiện, lỗi -------------------------------------
    def status(self) -> dict[str, bool]:
        raw = self._read("STATUS")[0]
        return {name: bool(raw & bit) for name, bit in regs_gen.STATUS_BITS.items()}

    def chg(self) -> dict[str, bool]:
        """Bit trạng thái bộ sạc (không bắt buộc cho máy trạng thái)."""
        raw = self._read("CHG")[0]
        return {name: bool(raw & bit) for name, bit in regs_gen.CHG_BITS.items()}

    def events(self) -> set[str]:
        """Đọc `EVENT`; MCU xóa các bit vừa trả về."""
        raw = self._read("EVENT")[0]
        return regs_gen.decode_event(raw)

    def fault(self) -> str:
        """Tên mã lỗi đang chốt; `NONE` khi không lỗi."""
        raw = self._read("FAULT_CODE")[0]
        name = regs_gen.FAULT_CODE_NAME.get(raw)
        if name is None:
            raise McuError(f"ma loi MCU khong xac dinh: {raw}")
        return name

    def sys_flags(self) -> dict[str, bool]:
        raw = self._read("SYS_FLAGS")[0]
        return {
            name: bool(raw & bit)
            for name, bit in regs_gen.SYS_FLAGS_BITS.items()
        }

    def boot_reason(self) -> str:
        """Nguyên nhân reset gần nhất theo thứ tự ưu tiên.

        Trả chuỗi ASCII thay vì đoán: `wdt_reset`, `por_bor`, `pin_reset`,
        `software`, `unknown`.
        """
        flags = self.sys_flags()
        for name in ("WDT_RESET", "POR_BOR", "PIN_RESET", "SOFTWARE"):
            if flags[name]:
                return name.lower()
        return "unknown"

    # -- đo lường ------------------------------------------------------
    def battery_mv(self) -> int:
        raw = self._read("VBAT_MV")
        return regs_gen.unpack(raw)

    def temps(self) -> tuple[int | None, int | None]:
        """(nhiệt độ pin, nhiệt độ môi trường); `None` khi cảm biến không đọc được."""
        bat = self._read("BAT_TEMP_C")[0]
        amb = self._read("AMB_TEMP_C")[0]
        return regs_gen.decode_int8(bat), regs_gen.decode_int8(amb)

    def uptime_s(self) -> int:
        return regs_gen.unpack(self._read("UPTIME_S"))

    def boot_count(self) -> int:
        return self._read("BOOT_COUNT")[0]

    # -- cấu hình ------------------------------------------------------
    def mode(self) -> str:
        raw = self._read("MODE")[0]
        name = regs_gen.MODE_NAME.get(raw)
        if name is None:
            raise McuError(f"che do MCU khong xac dinh: {raw}")
        return name.lower()

    def set_mode(self, mode: str) -> None:
        key = _normalise_mode(mode)
        self._write("MODE", bytes([regs_gen.MODE[key]]))

    def wake_in_s(self) -> int:
        return regs_gen.unpack(self._read("WAKE_IN_S"))

    def set_wake_in_s(self, seconds: int) -> None:
        value = _check_uint(seconds, "wake_in_s", 0, 0xFFFF_FFFF)
        self._write("WAKE_IN_S", regs_gen.pack(value, 4))

    def wake_chan(self) -> str:
        raw = self._read("WAKE_CHAN")[0]
        name = regs_gen.WAKE_CHAN_NAME.get(raw)
        if name is None:
            raise McuError(f"kenh danh thuc khong xac dinh: {raw}")
        return name.lower()

    def set_wake_chan(self, name: str) -> None:
        key = _normalise_wake_chan(name)
        self._write("WAKE_CHAN", bytes([regs_gen.WAKE_CHAN[key]]))

    def wake_period_s(self) -> int:
        return regs_gen.unpack(self._read("WAKE_PERIOD_S"))

    def set_wake_period_s(self, seconds: int) -> None:
        value = _check_uint(seconds, "wake_period_s", 0, 0xFFFF)
        self._write("WAKE_PERIOD_S", regs_gen.pack(value, 2))

    # -- lệnh ----------------------------------------------------------
    def cmd(self, name: str) -> None:
        key = name.upper()
        if key not in regs_gen.CMD:
            raise ValueError(f"lenh MCU khong ho tro: {name}")
        self._write("CMD", bytes([regs_gen.CMD[key]]))

    # -- khác ----------------------------------------------------------
    def irq_wait(self, timeout: float) -> bool:
        return self._link.irq_wait(timeout)

    def close(self) -> None:
        self._link.close()


def _normalise_mode(mode: str) -> str:
    key = str(mode).upper()
    if key not in regs_gen.MODE:
        allowed = ", ".join(sorted(name.lower() for name in regs_gen.MODE))
        raise ValueError(f"mode khong hop le: {mode!r}; cho phep: {allowed}")
    return key


def _normalise_wake_chan(name: str) -> str:
    key = str(name).upper()
    if key not in regs_gen.WAKE_CHAN:
        allowed = ", ".join(sorted(n.lower() for n in regs_gen.WAKE_CHAN))
        raise ValueError(f"wake_chan khong hop le: {name!r}; cho phep: {allowed}")
    return key


class MemoryMcu(McuLink):
    """Mô phỏng regmap trong bộ nhớ, độc lập với firmware C.

    Dùng cho test ứng dụng và sim. Có các hàm tiêm trạng thái (`raise_event`,
    `set_fault`, `set_battery_mv`, ...) để dựng kịch bản. `irq_wait` dùng
    `Clock` được tiêm nên không ngủ thật khi chạy test.
    """

    def __init__(
        self,
        clock: Clock | None = None,
        *,
        proto_ver: int = regs_gen.PROTO_VER,
        fw_ver: int | None = None,
    ) -> None:
        if fw_ver is None:
            # regs_gen không sinh hằng số FW_VER; reset nằm trong bảng REG_BY_NAME.
            fw_ver = regs_gen.REG_BY_NAME["FW_VER"].reset
        self._clock: Clock = clock if clock is not None else RealClock()
        self._regs = bytearray(regs_gen.REG_COUNT)
        for reg in regs_gen.REGISTERS:
            raw = reg.reset
            for offset in range(reg.size):
                shift = 8 * (reg.size - 1 - offset)
                self._regs[reg.addr + offset] = (raw >> shift) & 0xFF
        self._regs[regs_gen.REG_BY_NAME["PROTO_VER"].addr] = proto_ver & 0xFF
        self._regs[regs_gen.REG_BY_NAME["FW_VER"].addr] = fw_ver & 0xFF
        self._latched: dict[int, bytes] = {}
        self._pending: dict[int, bytearray] = {}
        self._irq_pending = False
        self._closed = False
        #: Tên các lệnh hợp lệ đã nhận, theo thứ tự.
        self.commands: list[str] = []
        #: Giá trị các lệnh CMD không hợp lệ đã nhận.
        self.bad_cmds: list[int] = []
        #: Số lần `irq_wait` được gọi (tiện cho test).
        self.irq_waits = 0

    # -- McuLink -------------------------------------------------------
    def read(self, addr: int, n: int = 1) -> bytes:
        self._check_open()
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("so byte doc phai >= 1")
        if addr < 0 or addr + n > regs_gen.REG_COUNT:
            raise McuNack(f"doc ngoai dai: addr=0x{addr:02X} n={n}")
        # Kiểm tra toàn dải trước khi trả bất kỳ byte nào.
        for offset in range(n):
            self._find_reg(addr + offset)
        return bytes(self._read_byte(addr + offset) for offset in range(n))

    def write(self, addr: int, data: bytes) -> None:
        self._check_open()
        payload = bytes(data)
        if not payload:
            raise ValueError("khong ghi 0 byte")
        if addr < 0 or addr + len(payload) > regs_gen.REG_COUNT:
            raise McuNack(f"ghi ngoai dai: addr=0x{addr:02X} n={len(payload)}")
        for offset, value in enumerate(payload):
            self._write_byte(addr + offset, value)

    def irq_wait(self, timeout: float) -> bool:
        self._check_open()
        if timeout < 0:
            raise ValueError("timeout am")
        self.irq_waits += 1
        if self._irq_pending:
            self._irq_pending = False
            return True
        if timeout <= 0:
            return False
        self._clock.sleep(timeout)
        if self._irq_pending:
            self._irq_pending = False
            return True
        return False

    def close(self) -> None:
        self._closed = True

    # -- nội bộ --------------------------------------------------------
    def _check_open(self) -> None:
        if self._closed:
            raise McuError("MCU link da dong")

    @staticmethod
    def _find_reg(addr: int) -> regs_gen.Reg:
        """Tìm thanh ghi chứa byte `addr` (kể cả byte giữa của nhóm nhiều byte)."""
        for reg in regs_gen.REGISTERS:
            if reg.addr <= addr < reg.addr + reg.size:
                return reg
        raise McuNack(f"thanh ghi khong dinh nghia: 0x{addr:02X}")

    def _read_byte(self, addr: int) -> int:
        reg = self._find_reg(addr)
        if reg.access == regs_gen.ACCESS_WO:
            raise McuNack(f"doc thanh ghi chi ghi: {reg.name}")
        if reg.clear_on_read:
            value = self._regs[addr]
            self._regs[addr] = 0
            return value
        if reg.size > 1:
            start = reg.addr
            if reg.latch_read:
                block = self._latched.get(start)
                if block is None:
                    block = bytes(self._regs[start:start + reg.size])
                    self._latched[start] = block
            else:
                block = bytes(self._regs[start:start + reg.size])
            return block[addr - start]
        return self._regs[addr]

    def _write_byte(self, addr: int, value: int) -> None:
        reg = self._find_reg(addr)
        if reg.access == regs_gen.ACCESS_RO:
            raise McuNack(f"ghi thanh ghi chi doc: {reg.name}")
        if reg.name == "CMD":
            self._handle_cmd(value)
            return
        if reg.commit_write and reg.size > 1:
            block = self._pending.get(reg.addr)
            if block is None:
                block = bytearray(self._regs[reg.addr:reg.addr + reg.size])
                self._pending[reg.addr] = block
            block[addr - reg.addr] = value
            if addr == reg.addr + reg.size - 1:
                self._regs[reg.addr:reg.addr + reg.size] = block
                del self._pending[reg.addr]
            return
        self._regs[addr] = value
        if reg.latch_read:
            # Giá trị mới chỉ thấy khi đọc lại byte cao (latch mới).
            self._latched.pop(reg.addr, None)

    def _handle_cmd(self, value: int) -> None:
        name = regs_gen.CMD_NAME.get(value)
        if name is None:
            self.bad_cmds.append(value)
            self._set_fault(regs_gen.FAULT_CODE["BAD_CMD"])
            return
        self.commands.append(name)
        status_addr = regs_gen.REG_BY_NAME["STATUS"].addr
        if name == "SOC_WAKE":
            self._regs[status_addr] |= regs_gen.STATUS_BITS["SOC_READY"]
        elif name == "SOC_SHUTDOWN_DONE":
            self._regs[status_addr] &= ~regs_gen.STATUS_BITS["SOC_POWER_ON"]
        elif name == "MODEM_ON":
            self._regs[status_addr] |= regs_gen.STATUS_BITS["MODEM_POWER_ON"]
        elif name == "MODEM_OFF":
            self._regs[status_addr] &= ~regs_gen.STATUS_BITS["MODEM_POWER_ON"]
        elif name == "CLEAR_FAULT":
            self._set_fault(regs_gen.FAULT_CODE["NONE"])

    def _set_fault(self, code: int) -> None:
        self._regs[regs_gen.REG_BY_NAME["FAULT_CODE"].addr] = code & 0xFF
        status_addr = regs_gen.REG_BY_NAME["STATUS"].addr
        if code:
            self._regs[status_addr] |= regs_gen.STATUS_BITS["FAULT"]
        else:
            self._regs[status_addr] &= ~regs_gen.STATUS_BITS["FAULT"]

    # -- hàm tiêm trạng thái cho test/sim ------------------------------
    def _status_bit(self, name: str) -> int:
        if name not in regs_gen.STATUS_BITS:
            raise ValueError(f"bit STATUS khong ton tai: {name}")
        return regs_gen.STATUS_BITS[name]

    def set_status(self, name: str, value: bool = True) -> None:
        bit = self._status_bit(name)
        addr = regs_gen.REG_BY_NAME["STATUS"].addr
        if value:
            self._regs[addr] |= bit
        else:
            self._regs[addr] &= ~bit

    def raise_event(self, names: str | set[str]) -> None:
        """Đặt bit EVENT và kéo IRQ (mô phỏng ngắt từ MCU)."""
        wanted = {names} if isinstance(names, str) else set(names)
        for name in wanted:
            if name not in regs_gen.EVENT_BITS:
                raise ValueError(f"su kien khong ton tai: {name}")
        raw = regs_gen.encode_event(wanted)
        self._regs[regs_gen.REG_BY_NAME["EVENT"].addr] |= raw
        self._irq_pending = True

    def set_charge(self, name: str, value: bool = True) -> None:
        if name not in regs_gen.CHG_BITS:
            raise ValueError(f"bit CHG khong ton tai: {name}")
        addr = regs_gen.REG_BY_NAME["CHG"].addr
        bit = regs_gen.CHG_BITS[name]
        if value:
            self._regs[addr] |= bit
        else:
            self._regs[addr] &= ~bit

    def set_fault(self, name: str | int) -> None:
        if isinstance(name, str):
            if name not in regs_gen.FAULT_CODE:
                raise ValueError(f"ma loi khong ton tai: {name}")
            self._set_fault(regs_gen.FAULT_CODE[name])
            return
        if isinstance(name, bool) or not isinstance(name, int):
            raise ValueError("ma loi phai la ten hoac so nguyen")
        if not 0 <= name <= 0xFF:
            raise ValueError("ma loi ngoai dai byte")
        self._set_fault(name)

    def set_battery_mv(self, mv: int) -> None:
        _check_uint(mv, "battery_mv", 0, 0xFFFF)
        addr = regs_gen.REG_BY_NAME["VBAT_MV"].addr
        self._regs[addr:addr + 2] = regs_gen.pack(mv, 2)
        self._latched.pop(addr, None)

    def set_temps(self, batt: int | None, amb: int | None) -> None:
        for name, value in (("BAT_TEMP_C", batt), ("AMB_TEMP_C", amb)):
            if value is None:
                raw = 0x80
            else:
                if not -128 <= value <= 127:
                    raise ValueError(f"{name} ngoai dai int8")
                raw = value & 0xFF
            self._regs[regs_gen.REG_BY_NAME[name].addr] = raw

    def set_sys_flags(self, names: set[str]) -> None:
        raw = 0
        for name in names:
            if name not in regs_gen.SYS_FLAGS_BITS:
                raise ValueError(f"co SYS_FLAGS khong ton tai: {name}")
            raw |= regs_gen.SYS_FLAGS_BITS[name]
        self._regs[regs_gen.REG_BY_NAME["SYS_FLAGS"].addr] = raw

    def set_uptime_s(self, seconds: int) -> None:
        _check_uint(seconds, "uptime_s", 0, 0xFFFF)
        addr = regs_gen.REG_BY_NAME["UPTIME_S"].addr
        self._regs[addr:addr + 2] = regs_gen.pack(seconds, 2)
        self._latched.pop(addr, None)

    def set_boot_count(self, count: int) -> None:
        _check_uint(count, "boot_count", 0, 0xFF)
        self._regs[regs_gen.REG_BY_NAME["BOOT_COUNT"].addr] = count

    @property
    def irq_pending(self) -> bool:
        return self._irq_pending


class I2cLink(McuLink):
    """Bus I2C Linux qua `/dev/i2c-N` bằng `fcntl.ioctl`.

    Cần phần cứng thật; chưa kiểm chứng với MCU STM32L0. `irq_wait` chưa hiện
    thực vì cần đường GPIO `MCU_IRQ` (xem docs/03 §3); gọi sẽ ném `McuError`
    thay vì trả `False` giả.
    """

    I2C_SLAVE = 0x0703
    I2C_RDWR = 0x0707
    I2C_M_RD = 0x0001

    def __init__(
        self,
        device: str = "/dev/i2c-1",
        address: int = regs_gen.I2C_ADDR,
    ) -> None:
        self._device = device
        self._address = address
        self._fd: int | None = None
        self._fcntl = None

    # -- mở/đóng -------------------------------------------------------
    def _ensure_open(self) -> None:
        if self._fd is not None:
            return
        if not sys.platform.startswith("linux"):
            raise McuError(
                "I2cLink chi ho tro Linux; nen tang hien tai la "
                f"{sys.platform}. Dung MemoryMcu cho test/sim."
            )
        try:
            import fcntl
        except ImportError as exc:  # pragma: no cover - Linux luôn có fcntl
            raise McuError("khong import duoc fcntl") from exc
        try:
            fd = os.open(self._device, os.O_RDWR)
        except OSError as exc:
            raise McuError(f"khong mo duoc {self._device}: {exc}") from exc
        try:
            fcntl.ioctl(fd, self.I2C_SLAVE, self._address)
        except OSError as exc:
            os.close(fd)
            raise McuError(
                f"khong dat duoc dia chi I2C 0x{self._address:02X}: {exc}"
            ) from exc
        self._fd = fd
        self._fcntl = fcntl

    def close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None

    # -- giao dịch -----------------------------------------------------
    def read(self, addr: int, n: int = 1) -> bytes:
        self._ensure_open()
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("so byte doc phai >= 1")
        import ctypes

        if not 0 <= addr <= 0xFF:
            raise ValueError("dia chi thanh ghi phai trong 0..255")
        write_buf = (ctypes.c_uint8 * 1)(addr)
        read_buf = (ctypes.c_uint8 * n)()
        messages = (_I2cMsg * 2)(
            _I2cMsg(self._address, 0, 1, write_buf),
            _I2cMsg(self._address, self.I2C_M_RD, n, read_buf),
        )
        ioctl_data = _I2cRdwrIoctlData(messages, 2)
        fcntl = self._fcntl
        if fcntl is None:
            raise McuError("fcntl khong kha dung")
        try:
            fcntl.ioctl(self._fd, self.I2C_RDWR, ctypes.addressof(ioctl_data))
        except OSError as exc:
            raise McuError(f"I2C read 0x{addr:02X}/{n} loi: {exc}") from exc
        return bytes(bytearray(read_buf))

    def write(self, addr: int, data: bytes) -> None:
        self._ensure_open()
        import ctypes

        payload = bytes(data)
        if not payload:
            raise ValueError("khong ghi 0 byte")
        if not 0 <= addr <= 0xFF:
            raise ValueError("dia chi thanh ghi phai trong 0..255")
        buf = (ctypes.c_uint8 * (len(payload) + 1))()
        buf[0] = addr
        for index, value in enumerate(payload):
            buf[index + 1] = value
        messages = (_I2cMsg * 1)(_I2cMsg(self._address, 0, len(payload) + 1, buf))
        ioctl_data = _I2cRdwrIoctlData(messages, 1)
        fcntl = self._fcntl
        if fcntl is None:
            raise McuError("fcntl khong kha dung")
        try:
            fcntl.ioctl(self._fd, self.I2C_RDWR, ctypes.addressof(ioctl_data))
        except OSError as exc:
            raise McuError(f"I2C write 0x{addr:02X}/{len(payload)} loi: {exc}") from exc

    def irq_wait(self, timeout: float) -> bool:
        raise McuError(
            "irq_wait chua hien thuc cho I2cLink: can duong GPIO MCU_IRQ "
            "(CHUA XAC MINH tren board that)"
        )


# Cấu trúc dữ liệu của ioctl I2C_RDWR. `ctypes` có sẵn trên mọi nền tảng nên
# định nghĩa ở mức module vẫn an toàn khi import trên Windows.
try:  # pragma: no cover - chỉ dùng khi có phần cứng
    import ctypes as _ctypes

    class _I2cMsg(_ctypes.Structure):
        _fields_ = [
            ("addr", _ctypes.c_uint16),
            ("flags", _ctypes.c_uint16),
            ("len", _ctypes.c_uint16),
            ("buf", _ctypes.POINTER(_ctypes.c_uint8)),
        ]

    class _I2cRdwrIoctlData(_ctypes.Structure):
        _fields_ = [
            ("msgs", _ctypes.POINTER(_I2cMsg)),
            ("nmsgs", _ctypes.c_uint32),
        ]

except Exception as _exc:  # pragma: no cover
    raise RuntimeError(f"khong dinh nghia duoc ctypes I2C: {_exc}") from _exc
