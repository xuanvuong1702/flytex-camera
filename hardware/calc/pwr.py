"""Tính toán thiết kế board PWR — chỉ thư viện chuẩn.

Mục đích: mọi giá trị linh kiện trong tài liệu phải tính lại được bằng máy, và
kiểm tra được các giới hạn (dòng bão hòa cuộn cảm, dải ADC, điểm cắt NTC, nhiệt).
Không có số đo nào ở đây: đầu vào là tham số thiết kế, không phải kết quả đo.

Chạy báo cáo: `python -m hardware.calc.cli` (hoặc `python hardware/calc/cli.py`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Dãy E96 (3 chữ số) để chọn điện trở có thật trên thị trường.
E96_MANTISSA = (
    100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130, 133, 137, 140, 143,
    147, 150, 154, 158, 162, 165, 169, 174, 178, 182, 187, 191, 196, 200, 205, 210,
    215, 221, 226, 232, 237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
    316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412, 422, 432, 442, 453,
    464, 475, 487, 499, 511, 523, 536, 549, 562, 576, 590, 604, 619, 634, 649, 665,
    681, 698, 715, 732, 750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976,
)


@dataclass(frozen=True)
class Divider:
    top_ohm: float
    bottom_ohm: float
    vout_v: float
    error_pct: float
    ratio: float


@dataclass(frozen=True)
class BoostCurrents:
    duty: float
    input_a: float
    inductor_avg_a: float
    ripple_pp_a: float
    peak_a: float
    rms_a: float


@dataclass(frozen=True)
class AdcInput:
    divider_ratio: float
    adc_mv_at_max: float
    mv_per_lsb: float
    headroom_v: float


def e96_values(low: float, high: float) -> list[float]:
    """Các giá trị E96 trong [low, high]."""
    if low <= 0 or high <= 0 or low > high:
        raise ValueError("dai gia tri khong hop le")
    values: list[float] = []
    decade = 1.0
    while decade <= high:
        for mantissa in E96_MANTISSA:
            value = mantissa / 100.0 * decade
            if low <= value <= high:
                values.append(value)
        decade *= 10.0
    return sorted(values)


def choose_divider(vout_v: float, vref_v: float, low_ohm: float = 10_000.0,
                   high_ohm: float = 1_000_000.0) -> Divider:
    """Chọn cặp điện trở E96 cho mạch hồi tiếp: Vout = Vref·(1 + Rt/Rb)."""
    if vout_v <= vref_v or vref_v <= 0:
        raise ValueError("vout phai lon hon vref")
    ratio = vout_v / vref_v - 1.0
    best: Divider | None = None
    for bottom in e96_values(low_ohm, high_ohm / max(ratio, 1.0)):
        ideal_top = ratio * bottom
        for top in (ideal_top * 0.98, ideal_top, ideal_top * 1.02):
            candidates = e96_values(max(low_ohm, top * 0.95), min(high_ohm, top * 1.05))
            for top_value in candidates:
                actual_ratio = top_value / bottom
                actual_vout = vref_v * (1.0 + actual_ratio)
                error = abs(actual_vout - vout_v) / vout_v * 100.0
                divider = Divider(top_value, bottom, actual_vout, error, actual_ratio)
                if best is None or divider.error_pct < best.error_pct:
                    best = divider
    if best is None:
        raise ValueError("khong tim duoc cap dien tro trong dai")
    return best


def boost_currents(vin_v: float, vout_v: float, iout_a: float, eta: float,
                   fsw_hz: float, inductance_h: float) -> BoostCurrents:
    """Dòng điện boost ở chế độ dẫn liên tục, bỏ qua tổn hao chi tiết."""
    if not 0.0 < eta <= 1.0:
        raise ValueError("eta phai trong (0, 1]")
    if vin_v <= 0 or vout_v <= 0 or iout_a < 0:
        raise ValueError("tham so khong hop le")
    if vin_v >= vout_v:
        raise ValueError("boost can vin < vout")
    if fsw_hz <= 0 or inductance_h <= 0:
        raise ValueError("fsw va L phai > 0")
    duty = 1.0 - (vin_v * eta / vout_v)
    input_a = vout_v * iout_a / (vin_v * eta)
    ripple = vin_v * duty / (inductance_h * fsw_hz)
    avg = input_a
    peak = avg + ripple / 2.0
    rms = math.sqrt(avg * avg + (ripple * ripple) / 12.0)
    return BoostCurrents(duty, input_a, avg, ripple, peak, rms)


def linear_charger_loss_w(vbus_v: float, vbat_v: float, current_a: float) -> float:
    if vbus_v <= vbat_v or current_a < 0:
        raise ValueError("vbus phai lon hon vbat, dong >= 0")
    return (vbus_v - vbat_v) * current_a


def charge_time_h(capacity_ah: float, current_a: float, soc_start: float = 0.2,
                  soc_end: float = 1.0, efficiency: float = 0.9) -> float:
    """Thời gian sạc từ soc_start tới soc_end, có hiệu suất sạc."""
    if capacity_ah <= 0 or current_a <= 0:
        raise ValueError("capacity va dong phai > 0")
    if not 0.0 <= soc_start < soc_end <= 1.0:
        raise ValueError("soc khong hop le")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency phai trong (0, 1]")
    energy_need_ah = capacity_ah * (soc_end - soc_start)
    return energy_need_ah / (current_a * efficiency)


def ntc_resistance_ohm(temp_c: float, r25_ohm: float = 10_000.0,
                       beta: float = 3950.0) -> float:
    """NTC B-parameter. Nhiệt độ tuyệt đối, mốc 25 °C."""
    if r25_ohm <= 0 or beta <= 0:
        raise ValueError("r25 va beta phai > 0")
    if temp_c <= -273.15:
        raise ValueError("nhiet do duoi 0 K")
    t_k = temp_c + 273.15
    t25_k = 298.15
    return r25_ohm * math.exp(beta * (1.0 / t_k - 1.0 / t25_k))


def ntc_ratio(temp_c: float, r25_ohm: float = 10_000.0, beta: float = 3950.0,
              r_pull_ohm: float = 7_150.0) -> float:
    """Tỉ lệ V_TEMP/VIN khi NTC nối đất, điện trở kéo lên VIN."""
    if r_pull_ohm <= 0:
        raise ValueError("r_pull phai > 0")
    r_ntc = ntc_resistance_ohm(temp_c, r25_ohm, beta)
    return r_ntc / (r_ntc + r_pull_ohm)


def ntc_temperature_at_ratio(ratio: float, r25_ohm: float = 10_000.0,
                             beta: float = 3950.0, r_pull_ohm: float = 7_150.0,
                             low_c: float = -40.0, high_c: float = 125.0) -> float:
    """Nhiệt độ tại đó tỉ lệ chia áp bằng `ratio` (hàm giảm theo nhiệt độ)."""
    if not 0.0 < ratio < 1.0:
        raise ValueError("ratio phai trong (0, 1)")

    def f(temp_c: float) -> float:
        return ntc_ratio(temp_c, r25_ohm, beta, r_pull_ohm) - ratio

    f_low, f_high = f(low_c), f(high_c)
    if f_low < 0 or f_high > 0:
        raise ValueError("ratio nam ngoai dai nhiet do")
    for _ in range(200):
        mid = (low_c + high_c) / 2.0
        value = f(mid)
        if abs(value) < 1e-12:
            return mid
        if value > 0:
            low_c = mid
        else:
            high_c = mid
    return (low_c + high_c) / 2.0


_E96 = (
    1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30,
    1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
    1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32,
    2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
    3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
    4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
    5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
    7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
)


def e96_nearest(value_ohm: float) -> float:
    """Giá trị E96 gần nhất trong cùng decade."""
    if value_ohm <= 0:
        raise ValueError("gia tri phai > 0")
    decade = 10.0 ** math.floor(math.log10(value_ohm))
    return min(_E96, key=lambda item: abs(item * decade - value_ohm)) * decade


def bq25070_ts_divider(r_hot_ohm: float, r_cold_ohm: float) -> tuple[float, float]:
    """R1 (LDO→TS) và R2 (TS→GND) cho BQ25070.

    TS = 12,5 % VLDO khi nóng và 25 % khi lạnh; NTC song song R2.
    Điều kiện: R1 = 7·(RHOT∥R2) = 3·(RCOLD∥R2).
    """
    if r_hot_ohm <= 0 or r_cold_ohm <= 0 or r_cold_ohm <= r_hot_ohm:
        raise ValueError("RCOLD phai lon hon RHOT")
    r2 = 4.0 * r_hot_ohm * r_cold_ohm / (3.0 * r_cold_ohm - 7.0 * r_hot_ohm)
    if r2 <= 0:
        raise ValueError("khong co nghiem R2 duong")
    parallel = r_hot_ohm * r2 / (r_hot_ohm + r2)
    return 7.0 * parallel, r2


def bq25070_ts_temperature(ratio: float, r1_ohm: float, r2_ohm: float,
                           r25_ohm: float = 10_000.0, beta: float = 3950.0,
                           low_c: float = -30.0, high_c: float = 80.0) -> float:
    """Nhiệt độ tại đó V_TS/V_LDO = ratio với mạng R1/R2/NTC của BQ25070."""
    if not 0.0 < ratio < 1.0 or r1_ohm <= 0 or r2_ohm <= 0:
        raise ValueError("tham so TS khong hop le")

    def f(temp_c: float) -> float:
        r_ntc = ntc_resistance_ohm(temp_c, r25_ohm, beta)
        parallel = r_ntc * r2_ohm / (r_ntc + r2_ohm)
        return parallel / (r1_ohm + parallel) - ratio

    if f(low_c) < 0 or f(high_c) > 0:
        raise ValueError("ratio nam ngoai dai nhiet do")
    for _ in range(200):
        mid = (low_c + high_c) / 2.0
        if abs(f(mid)) < 1e-12:
            return mid
        if f(mid) > 0:
            low_c = mid
        else:
            high_c = mid
    return (low_c + high_c) / 2.0


def battery_adc(vbat_max_v: float, vadc_ref_v: float, bits: int,
                r_top_ohm: float, r_bottom_ohm: float) -> AdcInput:
    """Kiểm mạch chia áp đo pin: không vượt rail ADC và đủ độ phân giải."""
    if vadc_ref_v <= 0 or bits < 8 or r_bottom_ohm <= 0 or r_top_ohm <= 0:
        raise ValueError("tham so ADC khong hop le")
    ratio = (r_top_ohm + r_bottom_ohm) / r_bottom_ohm
    adc_v = vbat_max_v / ratio
    if adc_v > vadc_ref_v:
        raise ValueError(
            f"dien ap ADC {adc_v:.3f} V vuot {vadc_ref_v:.3f} V: tang ti le chia"
        )
    lsb = vadc_ref_v / (2 ** bits - 1)
    return AdcInput(ratio, adc_v * 1000.0, lsb * ratio * 1000.0, vadc_ref_v - adc_v)


def thermal_rise_c(power_w: float, area_m2: float, h_w_m2k: float = 8.0) -> float:
    """Tăng nhiệt xấp xỉ của vỏ kín: ΔT = P / (h·A)."""
    if power_w < 0 or area_m2 <= 0 or h_w_m2k <= 0:
        raise ValueError("tham so nhiet khong hop le")
    return power_w / (area_m2 * h_w_m2k)


def surface_temp_c(power_w: float, area_m2: float, ambient_c: float,
                   h_w_m2k: float = 8.0) -> float:
    return ambient_c + thermal_rise_c(power_w, area_m2, h_w_m2k)


def pack_wh(capacity_ah: float, nominal_v: float, usable: float = 1.0) -> float:
    if capacity_ah <= 0 or nominal_v <= 0:
        raise ValueError("capacity va dien ap phai > 0")
    if not 0.0 < usable <= 1.0:
        raise ValueError("usable phai trong (0, 1]")
    return capacity_ah * nominal_v * usable
