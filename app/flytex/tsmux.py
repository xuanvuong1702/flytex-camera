"""MPEG-TS muxer tối giản cho H.264, chỉ thư viện chuẩn.

Vì sao cần: bản nháp dùng `RawMuxer` (chỉ bring-up), file ghi ra không phát được.
Prototype cần container thật để phát lại và kiểm tra clip.

Phạm vi có chủ đích:
- một chương trình, một luồng video H.264 (stream_type 0x1B);
- mỗi lần `write(pts, data)` là một access unit Annex-B;
- PAT/PMT lặp theo chu kỳ, PCR trên PID video, PTS 90 kHz.

Không hỗ trợ: audio, nhiều chương trình, mã hóa, timestamp B-frame đảo thứ tự
(encoder phải phát theo thứ tự hiển thị hoặc người gọi chịu trách nhiệm).
"""

from __future__ import annotations

import os
from pathlib import Path

from .recorder import Muxer, RecorderError

PACKET_SIZE = 188
SYNC_BYTE = 0x47
PTS_MASK = (1 << 33) - 1
VIDEO_STREAM_TYPE = 0x1B
AUD_NAL = b"\x00\x00\x01\x09\xf0"


class TsError(RecorderError):
    """Lỗi khi đóng gói MPEG-TS."""


def crc32_mpeg(data: bytes) -> int:
    """CRC-32/MPEG-2: poly 0x04C11DB7, init 0xFFFFFFFF, không phản xạ."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc & 0xFFFFFFFF


def encode_pts(pts: int) -> bytes:
    """5 byte PTS/PCR field, tiền tố 0010 và marker bit."""
    value = pts & PTS_MASK
    return bytes(
        [
            0x21 | (((value >> 30) & 0x07) << 1),
            (value >> 22) & 0xFF,
            0x01 | (((value >> 15) & 0x7F) << 1),
            (value >> 7) & 0xFF,
            0x01 | ((value & 0x7F) << 1),
        ]
    )


def encode_pcr(base90k: int) -> bytes:
    base = base90k & PTS_MASK
    ext = 0
    return bytes(
        [
            (base >> 25) & 0xFF,
            (base >> 17) & 0xFF,
            (base >> 9) & 0xFF,
            (base >> 1) & 0xFF,
            ((base & 0x01) << 7) | 0x7E | ((ext >> 8) & 0x01),
            ext & 0xFF,
        ]
    )


class TsMuxer(Muxer):
    """Đóng gói access unit H.264 thành MPEG-TS."""

    extension = "ts"

    def __init__(
        self,
        video_pid: int = 0x0100,
        pmt_pid: int = 0x1000,
        program_number: int = 1,
        psi_interval_s: float = 0.5,
        pcr_interval_s: float = 0.04,
    ) -> None:
        if not 0x0010 <= video_pid <= 0x1FFE:
            raise ValueError("video_pid ngoai dai")
        if not 0x0010 <= pmt_pid <= 0x1FFE:
            raise ValueError("pmt_pid ngoai dai")
        if pmt_pid == video_pid:
            raise ValueError("pmt_pid phai khac video_pid")
        if psi_interval_s <= 0 or pcr_interval_s <= 0:
            raise ValueError("chu ky phai > 0")
        self.video_pid = video_pid
        self.pmt_pid = pmt_pid
        self.program_number = program_number
        self.psi_interval_s = float(psi_interval_s)
        self.pcr_interval_s = float(pcr_interval_s)
        self._file = None  # type: ignore[assignment]
        self._bytes = 0
        self._cc: dict[int, int] = {}
        self._last_psi_s = 0.0
        self._last_pcr_s: float | None = None
        self._frames = 0

    # -- Muxer API ------------------------------------------------------
    def begin(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(target, "wb")
        self._bytes = 0
        self._cc = {}
        self._frames = 0
        self._last_psi_s = 0.0
        self._last_pcr_s = None
        self._write_psi(0.0)

    def write(self, pts: float, data: bytes) -> None:
        if self._file is None:
            raise TsError("chua goi begin")
        if not data:
            raise TsError("access unit rong")
        pts_s = float(pts)
        pts90 = int(round(pts_s * 90_000)) & PTS_MASK
        if pts_s - self._last_psi_s >= self.psi_interval_s:
            self._write_psi(pts_s)
        pcr = None
        if self._last_pcr_s is None or pts_s - self._last_pcr_s >= self.pcr_interval_s:
            pcr = pts90
            self._last_pcr_s = pts_s
        payload = self._with_aud(data)
        self._write_pes(payload, pts90, pcr)
        self._frames += 1

    def end(self) -> int:
        if self._file is None:
            return 0
        handle = self._file
        self._file = None
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        return self._bytes

    # -- nội bộ ---------------------------------------------------------
    @staticmethod
    def _with_aud(data: bytes) -> bytes:
        if data.startswith(AUD_NAL[:4]) or data.startswith(b"\x00\x00\x00\x01\x09"):
            return data
        return AUD_NAL + data

    def _emit(self, packet: bytes) -> None:
        if len(packet) != PACKET_SIZE:
            raise TsError(f"goi TS sai kich thuoc: {len(packet)}")
        assert self._file is not None
        self._file.write(packet)
        self._bytes += PACKET_SIZE

    def _packet(self, pid: int, payload: bytes, pusi: bool, pcr90: int | None) -> bytes:
        if len(payload) > 184:
            raise TsError("payload vuot 184 byte")
        af_total = PACKET_SIZE - 4 - len(payload)
        if af_total == 0:
            af_field = b""
            afc = 0b01
        elif af_total == 1:
            af_field = b"\x00"
            afc = 0b11
        else:
            content = bytearray()
            content.append(0x10 if pcr90 is not None else 0x00)
            if pcr90 is not None:
                content += encode_pcr(pcr90)
            stuffing = af_total - 1 - len(content)
            if stuffing < 0:
                raise TsError("khong du cho adaptation field")
            content += b"\xff" * stuffing
            af_field = bytes([len(content)]) + bytes(content)
            afc = 0b11
        cc = self._cc.get(pid, 0)
        self._cc[pid] = (cc + 1) & 0x0F
        header = bytes(
            [
                SYNC_BYTE,
                (0x40 if pusi else 0x00) | ((pid >> 8) & 0x1F),
                pid & 0xFF,
                (afc << 4) | cc,
            ]
        )
        packet = header + af_field + payload
        if len(packet) != PACKET_SIZE:
            raise TsError(f"goi TS sai kich thuoc: {len(packet)}")
        return packet

    def _emit_payload(self, pid: int, payload: bytes, pusi: bool,
                      pcr90: int | None = None) -> None:
        offset = 0
        first = True
        while first or offset < len(payload):
            first_packet = first
            room = 176 if (first_packet and pcr90 is not None) else 184
            chunk = payload[offset:offset + room]
            offset += len(chunk)
            packet = self._packet(
                pid,
                chunk,
                pusi=pusi and first_packet,
                pcr90=pcr90 if first_packet else None,
            )
            self._emit(packet)
            first = False
            if offset >= len(payload):
                break

    def _psi_section(self, table_id: int, body: bytes) -> bytes:
        section_length = len(body) + 4
        head = bytes(
            [
                table_id,
                0xB0 | ((section_length >> 8) & 0x0F),
                section_length & 0xFF,
            ]
        )
        section = head + body
        crc = crc32_mpeg(section)
        return section + crc.to_bytes(4, "big")

    def _pat(self) -> bytes:
        body = bytes(
            [
                0x00, 0x01,          # transport_stream_id
                0xC1,                # version 0, current_next 1
                0x00, 0x00,          # section_number, last_section_number
                0x00, self.program_number,
                0xE0 | ((self.pmt_pid >> 8) & 0x1F), self.pmt_pid & 0xFF,
            ]
        )
        return self._psi_section(0x00, body)

    def _pmt(self) -> bytes:
        body = bytes(
            [
                0x00, self.program_number,
                0xC1,
                0x00, 0x00,
                0xE0 | ((self.video_pid >> 8) & 0x1F), self.video_pid & 0xFF,
                0xF0, 0x00,          # program_info_length = 0
                VIDEO_STREAM_TYPE,
                0xE0 | ((self.video_pid >> 8) & 0x1F), self.video_pid & 0xFF,
                0xF0, 0x00,          # ES_info_length = 0
            ]
        )
        return self._psi_section(0x02, body)

    def _emit_section(self, pid: int, section: bytes) -> None:
        if len(section) + 1 > 184:
            raise TsError("section PSI qua lon cho mot goi")
        payload = b"\x00" + section + b"\xff" * (183 - len(section))
        self._emit(self._packet(pid, payload, pusi=True, pcr90=None))

    def _write_psi(self, pts_s: float) -> None:
        self._emit_section(0x0000, self._pat())
        self._emit_section(self.pmt_pid, self._pmt())
        self._last_psi_s = float(pts_s)

    def _pes(self, payload: bytes, pts90: int) -> bytes:
        pes_length = 8 + len(payload)
        if pes_length > 0xFFFF:
            pes_length = 0
        header = bytes(
            [
                0x00, 0x00, 0x01, 0xE0,
                (pes_length >> 8) & 0xFF, pes_length & 0xFF,
                0x80, 0x80, 0x05,
            ]
        ) + encode_pts(pts90)
        if len(header) != 14:
            raise TsError("PES header sai kich thuoc")
        return header + payload

    def _write_pes(self, payload: bytes, pts90: int, pcr90: int | None) -> None:
        pes = self._pes(payload, pts90)
        self._emit_payload(self.video_pid, pes, pusi=True, pcr90=pcr90)
