"""Test MPEG-TS muxer bằng parser độc lập viết trong test."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from _bootstrap import ROOT
except ImportError:  # pragma: no cover
    from app.tests._bootstrap import ROOT  # noqa: F401

from flytex.clock import FakeClock
from flytex.recorder import SegmentRecorder
from flytex.tsmux import TsError, TsMuxer, crc32_mpeg, encode_pts

PACKET = 188


def packets(data: bytes) -> list[bytes]:
    if len(data) % PACKET:
        raise AssertionError(f"độ dài file không chia hết 188: {len(data)}")
    result = []
    for offset in range(0, len(data), PACKET):
        chunk = data[offset:offset + PACKET]
        if chunk[0] != 0x47:
            raise AssertionError(f"sync byte sai ở offset {offset}")
        result.append(chunk)
    return result


def pid_of(packet: bytes) -> int:
    return ((packet[1] & 0x1F) << 8) | packet[2]


def payload_of(packet: bytes) -> bytes:
    afc = (packet[3] >> 4) & 0x03
    offset = 4
    if afc & 0b10:
        af_len = packet[4]
        offset = 5 + af_len
    return packet[offset:]


def section_of(packet: bytes) -> bytes:
    payload = payload_of(packet)
    pointer = payload[0]
    body = payload[1 + pointer:]
    body[0]
    section_length = ((body[1] & 0x0F) << 8) | body[2]
    section = body[: 3 + section_length]
    crc = int.from_bytes(section[-4:], "big")
    if crc32_mpeg(section[:-4]) != crc:
        raise AssertionError("CRC sai")
    return section


def parse_psi(packets_: list[bytes]) -> tuple[int, int, int]:
    pmt_pid = None
    video_pid = None
    pcr_pid = None
    for packet in packets_:
        pid = pid_of(packet)
        if pid == 0x0000:
            section = section_of(packet)
            if section[0] != 0x00:
                continue
            # body sau 3 byte header: tsid(2) ver(1) sec(1+1) rồi các chương trình
            body = section[3:-4]
            program = int.from_bytes(body[5:7], "big")
            if program:
                pmt_pid = ((body[7] & 0x1F) << 8) | body[8]
        elif pmt_pid is not None and pid == pmt_pid:
            section = section_of(packet)
            if section[0] != 0x02:
                continue
            body = section[3:-4]
            pcr_pid = ((body[5] & 0x1F) << 8) | body[6]
            program_info_len = ((body[7] & 0x0F) << 8) | body[8]
            stream = body[9 + program_info_len:]
            if stream[0] != 0x1B:
                raise AssertionError("stream_type không phải H.264")
            video_pid = ((stream[1] & 0x1F) << 8) | stream[2]
    if pmt_pid is None or video_pid is None or pcr_pid is None:
        raise AssertionError("thiếu PAT/PMT")
    return pmt_pid, video_pid, pcr_pid


def pes_units(packets_: list[bytes], video_pid: int) -> list[dict]:
    units: list[dict] = []
    current: dict | None = None
    for packet in packets_:
        if pid_of(packet) != video_pid:
            continue
        pusi = bool(packet[1] & 0x40)
        payload = payload_of(packet)
        if pusi:
            if not payload.startswith(b"\x00\x00\x01\xe0"):
                raise AssertionError("PUSI nhưng không phải PES video")
            pes_len = int.from_bytes(payload[4:6], "big")
            header_data_len = payload[8]
            flags = payload[7]
            pts = None
            if flags & 0x80:
                raw = payload[9:14]
                pts = (
                    ((raw[0] >> 1) & 0x07) << 30
                    | raw[1] << 22
                    | (raw[2] >> 1) << 15
                    | raw[3] << 7
                    | raw[4] >> 1
                )
            data_start = 9 + header_data_len
            current = {
                "pts": pts,
                "pes_len": pes_len,
                "data": payload[data_start:],
                "packets": 1,
                "pcr": pcr_of(packet),
            }
            units.append(current)
        elif current is not None:
            current["data"] += payload
            current["packets"] += 1
    return units


def pcr_of(packet: bytes) -> int | None:
    afc = (packet[3] >> 4) & 0x03
    if not afc & 0b10 or packet[4] < 7:
        return None
    content = packet[5:5 + packet[4]]
    if not content[0] & 0x10:
        return None
    base = (
        content[1] << 25
        | content[2] << 17
        | content[3] << 9
        | content[4] << 1
        | (content[5] >> 7)
    )
    return base


class TsMuxerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _mux(self, frames: list[tuple[float, bytes]], name: str = "a.ts") -> bytes:
        muxer = TsMuxer()
        path = self.root / name
        muxer.begin(str(path))
        for pts, data in frames:
            muxer.write(pts, data)
        size = muxer.end()
        raw = path.read_bytes()
        self.assertEqual(size, len(raw))
        return raw

    def test_file_structure_and_psi(self) -> None:
        raw = self._mux([(0.0, b"\x00\x00\x01\x65" + b"x" * 300)])
        chunks = packets(raw)
        pmt_pid, video_pid, pcr_pid = parse_psi(chunks)
        self.assertEqual(pmt_pid, 0x1000)
        self.assertEqual(video_pid, 0x0100)
        self.assertEqual(pcr_pid, video_pid)
        self.assertGreater(len(chunks), 3)

    def test_pes_pts_and_aud(self) -> None:
        raw = self._mux([
            (0.0, b"\x00\x00\x01\x65" + b"a" * 100),
            (0.05, b"\x00\x00\x01\x41" + b"b" * 100),
        ])
        chunks = packets(raw)
        _, video_pid, _ = parse_psi(chunks)
        units = pes_units(chunks, video_pid)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["pts"], 0)
        self.assertEqual(units[1]["pts"], 4500)
        for unit in units:
            self.assertTrue(unit["data"].startswith(b"\x00\x00\x01\x09"), "thiếu AUD")
        self.assertIsNotNone(units[0]["pcr"])
        self.assertIsNotNone(units[1]["pcr"])

    def test_pcr_only_occasionally(self) -> None:
        frames = [(index / 30.0, b"\x00\x00\x01\x65" + b"c" * 80) for index in range(12)]
        raw = self._mux(frames)
        chunks = packets(raw)
        _, video_pid, _ = parse_psi(chunks)
        units = pes_units(chunks, video_pid)
        with_pcr = [unit for unit in units if unit["pcr"] is not None]
        self.assertGreaterEqual(len(with_pcr), 2)
        self.assertLess(len(with_pcr), len(units))

    def test_large_access_unit_splits_and_uses_zero_length(self) -> None:
        frame = b"\x00\x00\x01\x65" + b"d" * 100_000
        raw = self._mux([(0.0, frame)])
        chunks = packets(raw)
        _, video_pid, _ = parse_psi(chunks)
        units = pes_units(chunks, video_pid)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["pes_len"], 0)
        self.assertGreater(units[0]["packets"], 100)

    def test_continuity_counters(self) -> None:
        raw = self._mux([
            (index / 30.0, b"\x00\x00\x01\x65" + b"e" * 500) for index in range(5)
        ])
        counters: dict[int, int] = {}
        for packet in packets(raw):
            pid = pid_of(packet)
            cc = packet[3] & 0x0F
            if pid in counters:
                self.assertEqual(cc, (counters[pid] + 1) & 0x0F, f"CC sai ở PID {pid:#x}")
            counters[pid] = cc

    def test_psi_repeats(self) -> None:
        frames = [(index * 0.5, b"\x00\x00\x01\x65" + b"f" * 90) for index in range(4)]
        raw = self._mux(frames)
        pats = [packet for packet in packets(raw) if pid_of(packet) == 0]
        self.assertGreaterEqual(len(pats), 3, "phải lặp PAT theo chu kỳ")

    def test_aud_not_duplicated(self) -> None:
        frame = b"\x00\x00\x01\x09\xf0\x00\x00\x01\x65" + b"g" * 50
        raw = self._mux([(0.0, frame)])
        chunks = packets(raw)
        _, video_pid, _ = parse_psi(chunks)
        data = pes_units(chunks, video_pid)[0]["data"]
        self.assertEqual(data.count(b"\x00\x00\x01\x09"), 1)

    def test_empty_begin_without_write(self) -> None:
        muxer = TsMuxer()
        path = self.root / "empty.ts"
        muxer.begin(str(path))
        size = muxer.end()
        self.assertEqual(size, len(path.read_bytes()))
        self.assertGreater(size, 0)

    def test_write_before_begin_raises(self) -> None:
        with self.assertRaises(TsError):
            TsMuxer().write(0.0, b"data")

    def test_empty_access_unit_rejected(self) -> None:
        muxer = TsMuxer()
        muxer.begin(str(self.root / "b.ts"))
        with self.assertRaises(TsError):
            muxer.write(0.0, b"")
        muxer.end()

    def test_invalid_pids_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TsMuxer(video_pid=0)
        with self.assertRaises(ValueError):
            TsMuxer(video_pid=0x0100, pmt_pid=0x0100)

    def test_pts_encoding_markers(self) -> None:
        raw = encode_pts(0)
        self.assertEqual(raw[0] & 0x01, 1)
        self.assertEqual(raw[2] & 0x01, 1)
        self.assertEqual(raw[4] & 0x01, 1)
        self.assertEqual(len(raw), 5)

    def test_crc_known_value(self) -> None:
        # CRC-32/MPEG-2 của chuỗi "123456789" là 0x0376E6E7.
        self.assertEqual(crc32_mpeg(b"123456789"), 0x0376E6E7)

    def test_recorder_produces_ts_segments(self) -> None:
        clock = FakeClock()
        recorder = SegmentRecorder(
            self.root / "clips", clock, TsMuxer(),
            segment_s=5.0, max_bytes=1 << 20, pin_budget_bytes=1 << 19,
        )
        recorder.start("0123456789abcdef")
        for index in range(5):
            clock.advance(0.2)
            recorder.write(index * 0.2, b"\x00\x00\x01\x65" + b"h" * 200)
        info = recorder.stop()
        self.assertTrue(info.segments)
        self.assertTrue(all(name.endswith(".ts") for name in info.segments))
        for name in info.segments:
            raw = (Path(info.path) / name).read_bytes()
            self.assertGreater(len(raw), 0)
            packets(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
