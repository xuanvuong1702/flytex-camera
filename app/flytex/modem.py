"""Giao tiếp modem 4G qua AT.

Một lệnh AT có **một deadline tuyệt đối**; nếu transport không trả lời trong
hạn thì `AtTimeout` được ném ra, không treo. URC được tách khỏi kết quả lệnh
và đưa vào callback `on_urc`.

Các lệnh TCP/IP dùng stack của modem:

- `AT+QIOPEN=1,<cid>,"TCP","<host>",<port>,0,1`
- `AT+QISEND=<cid>,<len>` rồi gửi dữ liệu thô
- `AT+QIRD=<cid>,<n>`
- `AT+QICLOSE=<cid>`

`attach_data`, `set_edrx`, `set_psm` và toàn bộ nhóm TCP/IP **CHƯA XÁC MINH**
trên EC200U-EU thật; cần kiểm bằng `AT+...=?` trên board. Đường dữ liệu chính
theo docs/05 §1 vẫn là USB (ECM/RNDIS), AT chỉ để điều khiển.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .clock import Clock, RealClock

__all__ = [
    "AtClient",
    "AtError",
    "AtTimeout",
    "FakeModem",
    "ModemError",
    "ModemTransport",
    "SmsMessage",
]


class ModemError(Exception):
    """Lỗi modem nói chung."""


class AtError(ModemError):
    """Modem trả `ERROR` hoặc `+CME ERROR`/`+CMS ERROR`."""

    def __init__(
        self,
        command: str,
        code: int | str | None = None,
        response: list[str] | None = None,
        detail: str = "",
    ) -> None:
        self.command = command
        self.code = code
        self.response = list(response or [])
        message = f"AT command failed: {command!r} code={code!r}"
        if detail:
            message += f" ({detail})"
        super().__init__(message)


class AtTimeout(AtError):
    """Không nhận được kết quả lệnh trong hạn."""

    def __init__(
        self,
        command: str,
        elapsed: float,
        partial: str = "",
        detail: str = "",
    ) -> None:
        self.elapsed = float(elapsed)
        self.partial = partial
        message = f"AT timeout after {self.elapsed:.2f}s: {command!r}"
        if partial:
            message += f" partial={partial!r}"
        super().__init__(command, "TIMEOUT", [], message if detail == "" else detail)


class ModemTransport(Protocol):
    """Kênh byte tới modem (UART hoặc giả lập)."""

    def write(self, data: bytes) -> None:
        """Ghi dữ liệu."""

    def read(self, n: int, timeout: float) -> bytes:
        """Đọc tối đa `n` byte; trả `b""` nếu hết hạn."""

    def flush(self) -> None:
        """Xóa dữ liệu chưa xử lý."""


class PwrKey(Protocol):
    """Xung PWRKEY do MCU điều khiển."""

    def pulse(self, ms: int) -> None:
        """Giữ PWRKEY mức thấp `ms` milli giây."""


@dataclass(frozen=True)
class SmsMessage:
    index: int
    number: str
    text: str
    status: str = ""


_URC_PREFIXES = (
    "RDY",
    "RING",
    "+CREG:",
    "+CGREG:",
    "+CEREG:",
    "+CMTI:",
    "+CMT:",
    "+CDS:",
    "+QIND:",
    "+QIURC:",
    "+QFIND:",
    "+QMTSTAT:",
    "+CGEV:",
    "+PDP:",
    "+QNETDEVSTATUS:",
    "+QUSIM:",
    "+CPIN:",
    "+QIOPEN:",
    "+QIRD:",
    "+QISEND:",
)


def _expected_prefix(command: str) -> str:
    text = command.strip()
    if text.upper().startswith("AT"):
        text = text[2:]
    end = len(text)
    for marker in ("=", "?", " "):
        index = text.find(marker)
        if index != -1 and index < end:
            end = index
    return text[:end]


def _is_final(line: str) -> bool:
    return (
        line == "OK" or line == "ERROR" or line.startswith(("+CME ERROR:", "+CMS ERROR:"))
    )


class AtClient:
    """Client AT có deadline thật, tách URC và điều khiển modem."""

    PWRKEY_PULSE_MS = 500
    PWRKEY_LONG_MS = 650

    def __init__(
        self,
        transport: ModemTransport,
        clock: Clock,
        on_urc: Callable[[str], None] | None = None,
        pwrkey: PwrKey | None = None,
        *,
        urc_history: int = 128,
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._on_urc = on_urc
        self._pwrkey = pwrkey
        self._buf = bytearray()
        self._urc_queue: deque[str] = deque(maxlen=urc_history)
        self._powered = False
        self._ready = False
        self.last_power_off_via: str | None = None
        self.last_power_off_error: str | None = None

    # -- thông tin -----------------------------------------------------
    @property
    def powered(self) -> bool:
        return self._powered

    @property
    def ready(self) -> bool:
        return self._ready

    def pending_urcs(self) -> list[str]:
        return list(self._urc_queue)

    # -- đọc dòng có deadline -----------------------------------------
    def _read_line(self, command: str, deadline: float, elapsed_from: float) -> str:
        while True:
            index = self._buf.find(b"\n")
            if index >= 0:
                raw = bytes(self._buf[:index])
                del self._buf[: index + 1]
                line = raw.decode("utf-8", errors="replace").strip("\r\n \t")
                if line:
                    return line
                continue
            remaining = deadline - self._clock.monotonic()
            if remaining <= 0:
                raise AtTimeout(
                    command,
                    elapsed=self._clock.monotonic() - elapsed_from,
                    partial=bytes(self._buf).decode("utf-8", errors="replace")[:80],
                )
            data = self._transport.read(4096, remaining)
            if data:
                self._buf.extend(data)
                continue
            # Transport không trả dữ liệu: nhường đồng hồ một chút để không
            # quay vòng CPU, rồi kiểm tra deadline.
            pause = min(0.05, deadline - self._clock.monotonic())
            if pause > 0:
                self._clock.sleep(pause)

    def _read_exact(
        self, count: int, command: str, deadline: float, elapsed_from: float
    ) -> bytes:
        while len(self._buf) < count:
            remaining = deadline - self._clock.monotonic()
            if remaining <= 0:
                raise AtTimeout(
                    command,
                    elapsed=self._clock.monotonic() - elapsed_from,
                    partial=f"can {count} byte, co {len(self._buf)}",
                )
            data = self._transport.read(4096, remaining)
            if data:
                self._buf.extend(data)
                continue
            pause = min(0.05, deadline - self._clock.monotonic())
            if pause > 0:
                self._clock.sleep(pause)
        result = bytes(self._buf[:count])
        del self._buf[:count]
        return result

    # -- URC -----------------------------------------------------------
    def _is_urc(self, line: str, expected: str) -> bool:
        if expected and (
            line == expected or line.startswith(expected + ":")
        ):
            return False
        return any(line.startswith(prefix) for prefix in _URC_PREFIXES)

    def _dispatch_urc(self, line: str) -> None:
        self._urc_queue.append(line)
        if self._on_urc is not None:
            self._on_urc(line)

    # -- lệnh ----------------------------------------------------------
    def command(
        self,
        cmd: str,
        timeout: float = 2.0,
        expect_ok: bool = True,
        *,
        _already_written: bool = False,
        _started_at: float | None = None,
    ) -> list[str]:
        """Gửi một lệnh AT và trả các dòng kết quả (không gồm echo và `OK`).

        `expect_ok=False` dùng cho lệnh có thể không trả `OK`: khi hết hạn,
        trả những dòng đã nhận thay vì ném `AtTimeout`.
        """
        if timeout <= 0:
            raise ValueError("timeout phai > 0")
        start = self._clock.monotonic() if _started_at is None else _started_at
        if not _already_written:
            self._transport.write((cmd + "\r").encode("ascii", errors="strict"))
        deadline = start + float(timeout)
        expected = _expected_prefix(cmd)
        result: list[str] = []
        try:
            while True:
                line = self._read_line(cmd, deadline, start)
                if line == cmd:
                    continue
                if line == "OK":
                    return result
                if line == "ERROR":
                    raise AtError(cmd, "ERROR", result)
                if line.startswith("+CME ERROR:"):
                    code = self._error_code(line)
                    raise AtError(cmd, code, result, "CME error")
                if line.startswith("+CMS ERROR:"):
                    code = self._error_code(line)
                    raise AtError(cmd, code, result, "CMS error")
                if self._is_urc(line, expected):
                    self._dispatch_urc(line)
                    continue
                result.append(line)
        except AtTimeout:
            if expect_ok:
                raise
            return result

    @staticmethod
    def _error_code(line: str) -> int | str:
        tail = line.split(":", 1)[1].strip() if ":" in line else ""
        try:
            return int(tail)
        except ValueError:
            return tail or "ERROR"

    def _wait_urc(self, prefix: str, timeout: float, command: str) -> str:
        for queued in list(self._urc_queue):
            if queued.startswith(prefix):
                try:
                    self._urc_queue.remove(queued)
                except ValueError:  # pragma: no cover - chỉ khi có race
                    pass
                return queued
        start = self._clock.monotonic()
        deadline = start + timeout
        while True:
            line = self._read_line(command, deadline, start)
            if line.startswith(prefix):
                return line
            if self._is_urc(line, ""):
                self._dispatch_urc(line)

    def _wait_prompt(self, prompt: bytes, timeout: float, command: str) -> None:
        start = self._clock.monotonic()
        deadline = start + timeout
        while True:
            index = self._buf.find(prompt)
            if index >= 0:
                del self._buf[: index + len(prompt)]
                return
            remaining = deadline - self._clock.monotonic()
            if remaining <= 0:
                raise AtTimeout(
                    command,
                    elapsed=self._clock.monotonic() - start,
                    partial="khong thay prompt",
                )
            data = self._transport.read(4096, remaining)
            if data:
                self._buf.extend(data)
                continue
            pause = min(0.05, deadline - self._clock.monotonic())
            if pause > 0:
                self._clock.sleep(pause)

    # -- nguồn ---------------------------------------------------------
    def power_on(self, timeout: float = 15.0) -> None:
        """Xung PWRKEY rồi chờ `RDY`; không ngủ thật khi dùng FakeClock."""
        if self._pwrkey is None:
            raise AtError(
                "PWRKEY",
                "NO_PWRKEY",
                detail="chua cau hinh PWRKEY; khong the bat modem",
            )
        self._pwrkey.pulse(self.PWRKEY_PULSE_MS)
        self.wait_ready(timeout)
        self._powered = True

    def power_off(self, timeout: float = 5.0) -> None:
        """Tắt modem: ưu tiên `AT+QPOWD`, dự phòng xung PWRKEY dài."""
        try:
            self.command("AT+QPOWD", timeout=timeout)
            self._powered = False
            self.last_power_off_via = "at"
            return
        except (AtError, AtTimeout) as exc:
            if self._pwrkey is None:
                raise
            self.last_power_off_error = str(exc)
            self._pwrkey.pulse(self.PWRKEY_LONG_MS)
            self._powered = False
            self.last_power_off_via = "pwrkey"

    def wait_ready(self, timeout: float = 15.0) -> None:
        """Chờ URC `RDY` sau khi cấp nguồn."""
        start = self._clock.monotonic()
        deadline = start + timeout
        while True:
            line = self._read_line("RDY", deadline, start)
            if line == "RDY":
                self._ready = True
                return
            if self._is_urc(line, ""):
                self._dispatch_urc(line)

    # -- SIM, mạng -----------------------------------------------------
    def sim_status(self) -> str:
        lines = self.command("AT+CPIN?")
        line = self._first_line(lines, "+CPIN:")
        if line is None:
            raise AtError("AT+CPIN?", "PARSE", lines, "thieu +CPIN")
        value = line.split(":", 1)[1].strip().lower().replace(" ", "_")
        return value

    def sim_ready(self) -> bool:
        return self.sim_status() == "ready"

    def registration(self) -> dict[str, object]:
        lines = self.command("AT+CREG?")
        line = self._first_line(lines, "+CREG:")
        if line is None:
            raise AtError("AT+CREG?", "PARSE", lines, "thieu +CREG")
        parts = [part.strip() for part in line.split(":", 1)[1].split(",")]
        if len(parts) < 2:
            raise AtError("AT+CREG?", "PARSE", lines, "thieu truong")
        try:
            mode = int(parts[0])
            stat = int(parts[1])
        except ValueError as exc:
            raise AtError("AT+CREG?", "PARSE", lines, "stat khong phai so") from exc
        return {
            "n": mode,
            "stat": stat,
            "registered": stat in (1, 5),
            "roaming": stat == 5,
            "lac": parts[2] if len(parts) > 2 else None,
            "ci": parts[3] if len(parts) > 3 else None,
        }

    def signal_dbm(self) -> int | None:
        """Đổi `+CSQ` sang dBm; 99 (không biết) trả `None`, không bịa số."""
        lines = self.command("AT+CSQ")
        line = self._first_line(lines, "+CSQ:")
        if line is None:
            raise AtError("AT+CSQ", "PARSE", lines, "thieu +CSQ")
        parts = line.split(":", 1)[1].split(",")
        try:
            rssi = int(parts[0].strip())
        except (ValueError, IndexError) as exc:
            raise AtError("AT+CSQ", "PARSE", lines, "rssi khong hop le") from exc
        if rssi == 99 or not 0 <= rssi <= 31:
            return None
        return -113 + 2 * rssi

    def operator(self) -> str | None:
        lines = self.command("AT+COPS?")
        line = self._first_line(lines, "+COPS:")
        if line is None:
            return None
        match = re.search(r'"([^"]*)"', line)
        return match.group(1) if match else None

    @staticmethod
    def _first_line(lines: list[str], prefix: str) -> str | None:
        for line in lines:
            if line.startswith(prefix):
                return line
        return None

    # -- dữ liệu -------------------------------------------------------
    def attach_data(self, apn: str) -> None:
        """Kích hoạt dữ liệu packet.

        CHƯA XÁC MINH: chuỗi lệnh dưới đây theo dòng Quectel EC200U nhưng
        chưa thử trên board thật. Cần đối chiếu `AT+QNETDEVCTL=?`,
        `AT+QICSGP=?` và cách kernel nhận interface ECM/RNDIS.
        """
        if not apn or len(apn) > 64:
            raise ValueError("APN rong hoac qua dai")
        if any(ord(char) < 0x20 or ord(char) > 0x7E for char in apn):
            raise ValueError("APN phai la ASCII in duoc")
        self.command(f'AT+CGDCONT=1,"IP","{apn}"')
        self.command(f'AT+QICSGP=1,1,"{apn}","","",1')
        self.command("AT+QNETDEVCTL=1,1,1", timeout=10.0)

    def set_edrx(
        self,
        enabled: bool,
        act_type: str = "0101",
        requested: str = "0001",
    ) -> None:
        """Bật/tắt eDRX (CHƯA XÁC MINH với EC200U-EU và nhà mạng)."""
        for name, value in (("act_type", act_type), ("requested", requested)):
            if not re.fullmatch(r"[01]{4}", value):
                raise ValueError(f"{name} phai la 4 bit nhi phan")
        if enabled:
            self.command(f'AT+QEDRXCFG=1,"{act_type}","{requested}"')
        else:
            self.command("AT+QEDRXCFG=0")

    def set_psm(
        self,
        enabled: bool,
        tau: str = "01000001",
        active: str = "00000001",
    ) -> None:
        """Bật/tắt PSM (CHƯA XÁC MINH với EC200U-EU và nhà mạng)."""
        for name, value in (("tau", tau), ("active", active)):
            if not re.fullmatch(r"[01]{8}", value):
                raise ValueError(f"{name} phai la 8 bit nhi phan")
        if enabled:
            self.command(f'AT+CPSMS=1,,"{tau}","{active}"')
        else:
            self.command("AT+CPSMS=0")

    # -- TCP/IP qua modem ----------------------------------------------
    def tcp_open(
        self,
        host: str,
        port: int,
        connect_id: int = 0,
        timeout: float = 10.0,
    ) -> int:
        """Mở kết nối TCP; trả `connect_id`. CHƯA XÁC MINH trên EC200U-EU."""
        if not host or len(host) > 128:
            raise ValueError("host rong hoac qua dai")
        if not 0 < int(port) < 65536:
            raise ValueError("port ngoai dai")
        command = (
            f'AT+QIOPEN=1,{int(connect_id)},"TCP","{host}",{int(port)},0,1'
        )
        lines = self.command(command, timeout=timeout)
        line = self._first_line(lines, "+QIOPEN:")
        if line is None:
            try:
                line = self._wait_urc("+QIOPEN:", timeout, command)
            except AtTimeout as exc:
                raise AtError(command, "NO_QIOPEN", lines, "thieu +QIOPEN") from exc
        parts = line.split(":", 1)[1].split(",")
        try:
            status = int(parts[1].strip())
        except (IndexError, ValueError) as exc:
            raise AtError(command, "PARSE", lines, "QIOPEN thieu status") from exc
        if status != 0:
            raise AtError(command, f"QIOPEN_{status}", lines, "tcp open failed")
        return int(connect_id)

    def tcp_send(
        self,
        data: bytes,
        connect_id: int = 0,
        timeout: float = 10.0,
    ) -> int:
        """Gửi dữ liệu qua kết nối modem. CHƯA XÁC MINH trên EC200U-EU."""
        payload = bytes(data)
        if not payload:
            return 0
        command = f"AT+QISEND={int(connect_id)},{len(payload)}"
        start = self._clock.monotonic()
        self._transport.write((command + "\r").encode("ascii"))
        self._wait_prompt(b">", timeout, command)
        self._transport.write(payload)
        deadline = start + timeout
        while True:
            line = self._read_line(command, deadline, start)
            if line == "SEND OK":
                return len(payload)
            if line == "SEND FAIL" or line == "ERROR":
                raise AtError(command, "SEND_FAIL", [line], "tcp send failed")
            if line.startswith("+CME ERROR:"):
                raise AtError(command, self._error_code(line), [line], "CME error")
            if self._is_urc(line, ""):
                self._dispatch_urc(line)

    def tcp_recv(
        self,
        max_bytes: int,
        connect_id: int = 0,
        timeout: float = 5.0,
    ) -> bytes:
        """Nhận dữ liệu. CHƯA XÁC MINH trên EC200U-EU; parse theo `+QIRD`."""
        if max_bytes <= 0:
            return b""
        command = f"AT+QIRD={int(connect_id)},{int(max_bytes)}"
        start = self._clock.monotonic()
        deadline = start + timeout
        self._transport.write((command + "\r").encode("ascii"))
        header: str | None = None
        while True:
            line = self._read_line(command, deadline, start)
            if line == "OK":
                return b""
            if line == "ERROR":
                raise AtError(command, "ERROR", [], "QIRD error")
            if line.startswith("+CME ERROR:"):
                raise AtError(command, self._error_code(line), [], "QIRD CME error")
            if line.startswith("+QIRD:"):
                header = line
                break
            if self._is_urc(line, "+QIRD"):
                self._dispatch_urc(line)
        parts = [part.strip() for part in header.split(":", 1)[1].split(",")]
        try:
            length = int(parts[-1]) if len(parts) >= 3 else int(parts[0])
        except (IndexError, ValueError) as exc:
            raise AtError(command, "PARSE", [header], "QIRD thieu do dai") from exc
        if length <= 0:
            return b""
        data = self._read_exact(length, command, deadline, start)
        # Bỏ dòng kết thúc (`OK`) sau dữ liệu nhị phân, nếu có.
        try:
            line = self._read_line(command, deadline, start)
            if line not in ("OK", ""):
                self._dispatch_urc(line)
        except AtTimeout:
            pass
        return data

    def tcp_close(self, connect_id: int = 0) -> None:
        """Đóng kết nối. CHƯA XÁC MINH trên EC200U-EU."""
        self.command(f"AT+QICLOSE={int(connect_id)}")

    # -- SMS -----------------------------------------------------------
    def sms_send(self, number: str, text: str, timeout: float = 30.0) -> int | None:
        """Gửi SMS dạng text (chỉ ASCII; UCS2 chưa hiện thực)."""
        if not re.fullmatch(r"\+?[0-9]{3,20}", number):
            raise ValueError("so dien thoai khong hop le")
        try:
            payload = text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "SMS chi ho tro ASCII; UCS2 chua hien thuc"
            ) from exc
        self.command("AT+CMGF=1")
        command = f'AT+CMGS="{number}"'
        start = self._clock.monotonic()
        self._transport.write((command + "\r").encode("ascii"))
        self._wait_prompt(b">", timeout, command)
        self._transport.write(payload + b"\x1a")
        lines = self.command(
            command,
            timeout=timeout,
            _already_written=True,
            _started_at=start,
        )
        reference: int | None = None
        for line in lines:
            if line.startswith("+CMGS:"):
                tail = line.split(":", 1)[1].strip()
                try:
                    reference = int(tail)
                except ValueError:
                    reference = None
        return reference

    def sms_read(self, index: int | None = None) -> list[SmsMessage]:
        """Đọc một SMS theo index hoặc toàn bộ (text mode). CHƯA XÁC MINH."""
        self.command("AT+CMGF=1")
        if index is not None:
            if index < 0:
                raise ValueError("index am")
            lines = self.command(f"AT+CMGR={int(index)}")
            return self._parse_sms_lines(lines, default_index=index)
        lines = self.command('AT+CMGL="ALL"')
        return self._parse_sms_lines(lines, default_index=None)

    @staticmethod
    def _parse_sms_lines(
        lines: list[str], default_index: int | None
    ) -> list[SmsMessage]:
        messages: list[SmsMessage] = []
        current: SmsMessage | None = None
        header_re = re.compile(
            r'^\+CMG[LR]:\s*(\d+)(?:,"([^"]*)")?(?:,"([^"]*)")?'
        )
        for line in lines:
            match = header_re.match(line)
            if match:
                index = int(match.group(1))
                status = match.group(2) or ""
                number = match.group(3) or ""
                current = SmsMessage(index=index, number=number, text="", status=status)
                messages.append(current)
                continue
            if current is not None and current.text == "":
                current = SmsMessage(
                    index=current.index,
                    number=current.number,
                    text=line,
                    status=current.status,
                )
                messages[-1] = current
            elif default_index is not None and not messages:
                messages.append(
                    SmsMessage(index=default_index, number="", text=line)
                )
        if default_index is not None and not messages and lines:
            messages.append(
                SmsMessage(index=default_index, number="", text="\n".join(lines))
            )
        return messages


class FakeModem:
    """Modem giả phản hồi kịch bản; có thể cài "treo" để test timeout.

    Mặc định modem **tắt nguồn** để test chuỗi PWRKEY. Gọi `set_powered(True)`
    hoặc dùng `AtClient.power_on()` trước khi gửi lệnh. `read` khi không có
    dữ liệu sẽ dịch `FakeClock` thay vì chặn thật.
    """

    def __init__(
        self,
        clock: Clock | None = None,
        *,
        powered: bool = False,
        echo: bool = True,
        rssi: int = 20,
        registered: bool = True,
        sim: str = "READY",
        operator_name: str = "FakeNet",
    ) -> None:
        self._clock: Clock = clock if clock is not None else RealClock()
        self._rx = bytearray()
        self._cmd_buf = bytearray()
        self._scripts: dict[str, list[str]] = {}
        self._hangs: set[str] = set()
        self._urc_during: dict[str, list[str]] = {}
        self._prompt_mode: str | None = None
        self._payload = bytearray()
        self._payload_expected = 0
        self._sms_text = bytearray()
        self._sms_number = ""
        self.powered = bool(powered)
        self.echo = bool(echo)
        self.rssi = int(rssi)
        self.registered = bool(registered)
        self.sim = str(sim)
        self.operator_name = str(operator_name)
        self.commands: list[str] = []
        self.raw_writes: list[bytes] = []
        self.power_pulses: list[int] = []
        self.sms_sent: list[dict[str, str]] = []
        self.tcp_payloads: list[bytes] = []

    # -- cấu hình kịch bản --------------------------------------------
    def set_response(self, command: str, lines: list[str] | None) -> None:
        if lines is None:
            self._scripts.pop(command, None)
        else:
            self._scripts[command] = list(lines)

    def hang(self, command: str, enabled: bool = True) -> None:
        """Không trả lời `command` (chỉ echo), buộc client timeout."""
        if enabled:
            self._hangs.add(command)
        else:
            self._hangs.discard(command)

    def inject_urc(self, line: str) -> None:
        self._rx.extend(line.encode("utf-8") + b"\r\n")

    def inject_urc_during(self, command: str, lines: list[str]) -> None:
        self._urc_during[command] = list(lines)

    def set_powered(self, value: bool) -> None:
        self.powered = bool(value)

    def set_signal(self, rssi: int) -> None:
        self.rssi = int(rssi)

    def set_registered(self, value: bool) -> None:
        self.registered = bool(value)

    # -- ModemTransport ------------------------------------------------
    def write(self, data: bytes) -> None:
        payload = bytes(data)
        self.raw_writes.append(payload)
        if self._prompt_mode == "sms":
            self._sms_text.extend(payload)
            if b"\x1a" in self._sms_text:
                text = bytes(self._sms_text).split(b"\x1a", 1)[0]
                self.sms_sent.append(
                    {
                        "number": self._sms_number,
                        "text": text.decode("utf-8", errors="replace"),
                    }
                )
                self._sms_text = bytearray()
                self._prompt_mode = None
                self._sms_number = ""
                self._queue_lines([f"+CMGS: {len(self.sms_sent)}", "OK"])
            return
        if self._prompt_mode == "qisend":
            self._payload.extend(payload)
            if len(self._payload) >= self._payload_expected:
                self.tcp_payloads.append(bytes(self._payload))
                self._payload = bytearray()
                self._payload_expected = 0
                self._prompt_mode = None
                self._queue_lines(["SEND OK"])
            return
        self._cmd_buf.extend(payload)
        while b"\r" in self._cmd_buf:
            index = self._cmd_buf.find(b"\r")
            raw = bytes(self._cmd_buf[:index])
            del self._cmd_buf[: index + 1]
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self._handle_command(line)

    def read(self, n: int, timeout: float) -> bytes:
        if n <= 0:
            return b""
        if self._rx:
            chunk = bytes(self._rx[:n])
            del self._rx[:n]
            return chunk
        # Không có dữ liệu: dịch đồng hồ đúng bằng timeout như một read thật
        # bị chặn, để AtClient thấy deadline đã hết và ném AtTimeout.
        if timeout > 0:
            self._clock.sleep(timeout)
        return b""

    def flush(self) -> None:
        self._rx.clear()

    # -- PwrKey --------------------------------------------------------
    def pulse(self, ms: int) -> None:
        self.power_pulses.append(int(ms))
        self.powered = not self.powered
        if self.powered:
            self._queue_lines(["RDY"])

    # -- xử lý lệnh ----------------------------------------------------
    def _handle_command(self, command: str) -> None:
        self.commands.append(command)
        upper = command.upper()
        if self.echo:
            self._queue_lines([command])
        if not self.powered:
            return
        if upper.startswith("ATE0"):
            self.echo = False
            self._queue_lines(["OK"])
            return
        if command in self._hangs:
            return
        if upper.startswith("AT+QISEND"):
            self._start_qisend(command)
            return
        if upper.startswith("AT+CMGS"):
            self._prompt_mode = "sms"
            match = re.search(r'"([^"]*)"', command)
            self._sms_number = match.group(1) if match else ""
            self._rx.extend(b"> ")
            return
        if upper.startswith("AT+QIRD"):
            self._handle_qird(command)
            return
        script = self._find_script(command)
        if script is not None:
            lines = list(script)
        else:
            lines = self._builtin_lines(command, upper)
        for urc in self._urc_during.get(command, []):
            self._queue_lines([urc])
        if upper == "AT+QPOWD":
            self._queue_lines(lines)
            self._queue_lines(["OK"])
            self.powered = False
            return
        if not self._has_final(lines):
            lines = lines + ["OK"]
        self._queue_lines(lines)

    def _find_script(self, command: str) -> list[str] | None:
        if command in self._scripts:
            return self._scripts[command]
        best: str | None = None
        for key in self._scripts:
            if key and command.startswith(key) and (best is None or len(key) > len(best)):
                best = key
        return self._scripts[best] if best is not None else None

    def _builtin_lines(self, command: str, upper: str) -> list[str]:
        if upper == "AT":
            return []
        if upper == "AT+CPIN?":
            return [f"+CPIN: {self.sim}"]
        if upper == "AT+CREG?" or upper == "AT+CGREG?":
            prefix = "CREG" if "CREG" in upper and "CGREG" not in upper else "CGREG"
            stat = 1 if self.registered else 2
            return [f"+{prefix}: 0,{stat}"]
        if upper == "AT+CEREG?":
            stat = 1 if self.registered else 2
            return [f"+CEREG: 0,{stat}"]
        if upper == "AT+CSQ":
            return [f"+CSQ: {self.rssi},99"]
        if upper == "AT+COPS?":
            return [f'+COPS: 0,0,"{self.operator_name}",7']
        if upper == "AT+CGMI":
            return ["Quectel"]
        if upper == "AT+CGMM":
            return ["FakeModem"]
        if upper == "AT+CGMR":
            return ["FAKE-REV-0.1"]
        if upper.startswith("AT+QIOPEN"):
            match = re.search(r"AT\+QIOPEN=\d+,(\d+),", command, re.IGNORECASE)
            connect_id = match.group(1) if match else "0"
            return [f"+QIOPEN: {connect_id},0"]
        if upper.startswith(("AT+QICLOSE", "AT+CGDCONT", "AT+QICSGP",
                             "AT+QNETDEVCTL", "AT+QEDRXCFG", "AT+CPSMS",
                             "AT+CMGF", "AT+CSCS")):
            return []
        return []

    def _start_qisend(self, command: str) -> None:
        try:
            self._payload_expected = int(command.rsplit(",", 1)[1])
        except (IndexError, ValueError):
            self._payload_expected = 0
        self._payload = bytearray()
        self._prompt_mode = "qisend"
        self._rx.extend(b"> ")

    def _handle_qird(self, command: str) -> None:
        match = re.search(r"AT\+QIRD=\d+,(\d+)", command, re.IGNORECASE)
        requested = int(match.group(1)) if match else 0
        data = b"" if requested <= 0 else b"Q" * min(requested, 8)
        self._queue_lines([f"+QIRD: {len(data)}"])
        self._rx.extend(data)
        self._queue_lines(["OK"])

    @staticmethod
    def _has_final(lines: list[str]) -> bool:
        return any(_is_final(line) for line in lines)

    def _queue_lines(self, lines: list[str]) -> None:
        for line in lines:
            self._rx.extend(line.encode("utf-8") + b"\r\n")
