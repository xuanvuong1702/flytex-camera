"""Nhập file CSV xuất từ Nordic Power Profiler Kit II (PPK2).

PPK2 xuất nhiều biến thể cột tuỳ phiên bản và ngôn ngữ. Module này chỉ dựa vào
tên cột có chứa "time", "current", "voltage" và đơn vị trong ngoặc, nên chấp
nhận được các biến thể thường gặp.

Không phụ thuộc thư viện ngoài; không tự đoán đơn vị: nếu không thấy đơn vị thì
mặc định là giây, mili-ampe, vôn và ghi rõ trong kết quả.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from pathlib import Path


class Ppk2Error(Exception):
    """File PPK2 không đọc được hoặc thiếu cột bắt buộc."""


@dataclass
class Ppk2Trace:
    samples: list[tuple[float, float, float | None]] = field(default_factory=list)
    time_unit: str = "s"
    current_unit: str = "mA"
    voltage_unit: str | None = None
    assumed_units: bool = False

    @property
    def duration_s(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return max(0.0, self.samples[-1][0] - self.samples[0][0])

    @property
    def mean_ma(self) -> float:
        if not self.samples:
            return 0.0
        charge = self._integral(lambda voltage: 1.0)  # mAs
        duration = self.duration_s
        if duration <= 0:
            return sum(sample[1] for sample in self.samples) / len(self.samples)
        return charge / duration

    @property
    def min_ma(self) -> float:
        return min((sample[1] for sample in self.samples), default=0.0)

    @property
    def max_ma(self) -> float:
        return max((sample[1] for sample in self.samples), default=0.0)

    @property
    def charge_mah(self) -> float:
        """Điện lượng tích phân, mAh (mAs / 3,6)."""
        return self._integral(lambda voltage: 1.0) / 3.6

    @property
    def energy_mwh(self) -> float | None:
        """Năng lượng tích phân, mWh; None nếu file không có cột điện áp."""
        if self.voltage_unit is None or any(sample[2] is None for sample in self.samples):
            return None
        return self._integral(lambda voltage: voltage) / 3.6

    def _integral(self, weight) -> float:
        if len(self.samples) < 2:
            return 0.0
        total = 0.0
        for (t0, i0, v0), (t1, i1, v1) in zip(self.samples, self.samples[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            w0 = weight(v0 if v0 is not None else 0.0)
            w1 = weight(v1 if v1 is not None else 0.0)
            total += 0.5 * (i0 * w0 + i1 * w1) * dt
        return total


def _split_delimiter(header_line: str) -> str:
    if header_line.count(";") >= header_line.count(","):
        return ";"
    return ","


def _unit_of(column: str, default: str) -> tuple[str, bool]:
    lowered = column.lower()
    start = lowered.find("(")
    end = lowered.find(")", start + 1)
    if start >= 0 and end > start:
        return lowered[start + 1:end].strip(), False
    return default, True


def _to_float(text: str, delimiter: str) -> float:
    value = text.strip()
    if not value:
        raise ValueError("empty")
    if delimiter == ";":
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")
    return float(value)


def _time_to_s(value: float, unit: str) -> float:
    return {
        "s": value,
        "sec": value,
        "ms": value / 1e3,
        "us": value / 1e6,
        "µs": value / 1e6,
    }[unit]


def _current_to_ma(value: float, unit: str) -> float:
    return {
        "a": value * 1e3,
        "ma": value,
        "ua": value / 1e3,
        "µa": value / 1e3,
    }[unit]


def _voltage_to_v(value: float, unit: str) -> float:
    return {"v": value, "mv": value / 1e3}[unit]


_ALLOWED_TIME = {"s", "sec", "ms", "us", "µs"}
_ALLOWED_CURRENT = {"a", "ma", "ua", "µa"}
_ALLOWED_VOLTAGE = {"v", "mv"}


def parse_csv(text: str) -> Ppk2Trace:
    if not text.strip():
        raise Ppk2Error("file rong")
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    header_index = None
    header = ""
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "time" in lowered and "current" in lowered:
            header_index = index
            header = line
            break
    if header_index is None:
        raise Ppk2Error("khong tim thay dong tieu de co time va current")
    delimiter = _split_delimiter(header)
    reader = list(csv.reader(io.StringIO("\n".join(lines[header_index:])), delimiter=delimiter))
    columns = [cell.strip() for cell in reader[0]]
    lowered = [cell.lower() for cell in columns]

    def find(name: str) -> int | None:
        for position, cell in enumerate(lowered):
            if name in cell:
                return position
        return None

    time_col = find("time")
    current_col = find("current")
    voltage_col = find("voltage")
    if time_col is None or current_col is None:
        raise Ppk2Error("thieu cot time hoac current")
    if voltage_col is None:
        for position, cell in enumerate(lowered):
            if cell.startswith("v") and "volt" not in cell and "v(" in cell:
                voltage_col = position
                break

    time_unit, assumed_time = _unit_of(columns[time_col], "s")
    current_unit, assumed_current = _unit_of(columns[current_col], "mA")
    voltage_unit = None
    assumed_voltage = False
    if voltage_col is not None:
        voltage_unit, assumed_voltage = _unit_of(columns[voltage_col], "V")
    if time_unit not in _ALLOWED_TIME:
        raise Ppk2Error(f"don vi thoi gian khong ho tro: {time_unit}")
    if current_unit not in _ALLOWED_CURRENT:
        raise Ppk2Error(f"don vi dong khong ho tro: {current_unit}")
    if voltage_unit is not None and voltage_unit not in _ALLOWED_VOLTAGE:
        raise Ppk2Error(f"don vi dien ap khong ho tro: {voltage_unit}")

    trace = Ppk2Trace(
        time_unit=time_unit,
        current_unit=current_unit,
        voltage_unit=voltage_unit,
        assumed_units=assumed_time or assumed_current or assumed_voltage,
    )
    for row in reader[1:]:
        if not row or all(not cell.strip() for cell in row):
            continue
        try:
            t_s = _time_to_s(_to_float(row[time_col], delimiter), time_unit)
            current_ma = _current_to_ma(_to_float(row[current_col], delimiter), current_unit)
            voltage_v = None
            if voltage_col is not None and voltage_col < len(row):
                raw = row[voltage_col].strip()
                if raw:
                    voltage_v = _voltage_to_v(_to_float(raw, delimiter), voltage_unit or "V")
        except (ValueError, IndexError, KeyError):
            continue
        if not math.isfinite(t_s) or not math.isfinite(current_ma):
            continue
        if voltage_v is not None and not math.isfinite(voltage_v):
            voltage_v = None
        trace.samples.append((t_s, current_ma, voltage_v))
    if not trace.samples:
        raise Ppk2Error("khong co mau hop le")
    trace.samples.sort(key=lambda sample: sample[0])
    first = trace.samples[0][0]
    if first != 0.0:
        trace.samples = [(t - first, i, v) for t, i, v in trace.samples]
    return trace


def load(path: str | Path) -> Ppk2Trace:
    return parse_csv(Path(path).read_text(encoding="utf-8", errors="replace"))


def to_measurements(
    trace: Ppk2Trace,
    measurement_id: str,
    *,
    date: str = "",
    board_rev: str = "",
    condition: str = "",
    instrument: str = "PPK2",
    notes: str = "",
) -> list[dict]:
    """Chuyển thành các dòng đúng lược đồ CSV của `tools.measure`."""
    rows = [
        {
            "id": measurement_id,
            "date": date,
            "board_rev": board_rev,
            "condition": condition,
            "instrument": instrument,
            "quantity": "current",
            "value": f"{trace.mean_ma:.3f}",
            "unit": "mA",
            "uncertainty_pct": "",
            "pass_fail": "INFO",
            "notes": (notes + " | trung binh PPK2").strip(" |"),
        },
        {
            "id": measurement_id,
            "date": date,
            "board_rev": board_rev,
            "condition": condition,
            "instrument": instrument,
            "quantity": "capacity",
            "value": f"{trace.charge_mah:.3f}",
            "unit": "mAh",
            "uncertainty_pct": "",
            "pass_fail": "INFO",
            "notes": (notes + " | dien luong tich phan").strip(" |"),
        },
    ]
    energy = trace.energy_mwh
    if energy is not None:
        rows.append(
            {
                "id": measurement_id,
                "date": date,
                "board_rev": board_rev,
                "condition": condition,
                "instrument": instrument,
                "quantity": "energy",
                "value": f"{energy:.3f}",
                "unit": "mWh",
                "uncertainty_pct": "",
                "pass_fail": "INFO",
                "notes": (notes + " | nang luong tich phan").strip(" |"),
            }
        )
    return rows
