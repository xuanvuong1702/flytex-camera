"""Tham số thiết kế PWR Rev A và các kiểm tra tự động.

Đây là nguồn sự thật cho các con số linh kiện trong `hardware/pwr-design.md`.
Giá trị nào lấy từ datasheet mà chưa đối chiếu đều ghi rõ "chua_xac_minh".
"""

from __future__ import annotations

from dataclasses import dataclass

from . import pwr

# --- Tham số thiết kế -------------------------------------------------------

BOOST = {
    "ic": "TPS61088",
    "vin_min_v": 3.0,
    "vin_nom_v": 3.2,
    "vout_v": 5.0,
    "vref_v": 1.204,          # chua_xac_minh: đối chiếu datasheet TPS61088
    "fsw_hz": 597_000.0,      # theo Rfsw 267k, chua_xac_minh
    "inductance_h": 1.2e-6,
    "eta": 0.90,
    "iout_max_a": 3.0,
    "inductor_isat_a": 9.0,
    "current_limit_a": 8.47,  # theo Rilim 64,9k, chua_xac_minh
}

BUCK = {
    "ic": "TPS62840",
    "vout_v": 3.3,
    "vref_v": None,           # chua_xac_minh: phải lấy từ datasheet gói DLC
    "iout_max_a": 0.75,
}

CHARGER = {
    # 2026-11-09: BQ25798 bi loai (mac dinh 4,2 V + watchdog). Chua chon IC moi.
    "topology": "CHUA CHON IC - yeu cau float 3,6 V bang phan cung + power-path",
    "vbus_v": 5.0,
    "vbat_v": 3.6,
    "current_a": 1.5,
    "capacity_ah": 15.0,
    "soc_start": 0.20,
    "efficiency": 0.90,
    "selected": False,
}

NTC = {
    # Tam hoan 2026-11-09: bang 7,15 kΩ / 42,5-47,5 % VIN la cua IC CAM4G cu,
    # khong ap dung cho IC sac moi. Chi tinh lai sau khi chon IC.
    "suspended": True,
    "r25_ohm": 10_000.0,
    "beta": 3950.0,
    "r_pull_ohm": 7_150.0,
    "threshold_hot_ratio": 0.425,
    "threshold_cold_ratio": 0.475,
    "expected_hot_min_c": 35.0,
    "expected_hot_max_c": 42.0,
}

BATTERY_ADC = {
    "vbat_max_v": 3.65,
    "vadc_ref_v": 3.3,
    "bits": 12,
    "r_top_ohm": 100_000.0,
    "r_bottom_ohm": 100_000.0,
    "max_mv_per_lsb": 5.0,
}

THERMAL = {
    "area_m2": 0.0372,
    "h_w_m2k": 8.0,
    "dissipation_w": 3.8,
    "ambient_c": 45.0,
    "max_surface_c": 60.0,
}

PACK = {
    "capacity_ah": 15.0,
    "nominal_v": 3.2,
    "usable_fraction": 0.85,
    "night_power_w": 3.8,
    "night_hours": 7.0,
    "min_margin": 1.30,
}


@dataclass(frozen=True)
class Check:
    name: str
    value: str
    limit: str
    passed: bool


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def design_values() -> dict[str, object]:
    """Tính toàn bộ giá trị thiết kế từ tham số ở trên."""
    divider = pwr.choose_divider(BOOST["vout_v"], BOOST["vref_v"])
    currents_min = pwr.boost_currents(
        BOOST["vin_min_v"], BOOST["vout_v"], BOOST["iout_max_a"],
        BOOST["eta"], BOOST["fsw_hz"], BOOST["inductance_h"],
    )
    currents_nom = pwr.boost_currents(
        BOOST["vin_nom_v"], BOOST["vout_v"], BOOST["iout_max_a"],
        BOOST["eta"], BOOST["fsw_hz"], BOOST["inductance_h"],
    )
    linear_loss = pwr.linear_charger_loss_w(
        CHARGER["vbus_v"], CHARGER["vbat_v"], CHARGER["current_a"]
    )
    switching_loss = (
        CHARGER["vbus_v"] * CHARGER["current_a"]
        * (1.0 - CHARGER["efficiency"])
    )
    charge_h = pwr.charge_time_h(
        CHARGER["capacity_ah"], CHARGER["current_a"],
        CHARGER["soc_start"], 1.0, CHARGER["efficiency"],
    )
    hot_c = pwr.ntc_temperature_at_ratio(
        NTC["threshold_hot_ratio"], NTC["r25_ohm"], NTC["beta"], NTC["r_pull_ohm"]
    )
    cold_c = pwr.ntc_temperature_at_ratio(
        NTC["threshold_cold_ratio"], NTC["r25_ohm"], NTC["beta"], NTC["r_pull_ohm"]
    )
    adc = pwr.battery_adc(
        BATTERY_ADC["vbat_max_v"], BATTERY_ADC["vadc_ref_v"], BATTERY_ADC["bits"],
        BATTERY_ADC["r_top_ohm"], BATTERY_ADC["r_bottom_ohm"],
    )
    surface_c = pwr.surface_temp_c(
        THERMAL["dissipation_w"], THERMAL["area_m2"],
        THERMAL["ambient_c"], THERMAL["h_w_m2k"],
    )
    pack_wh = pwr.pack_wh(
        PACK["capacity_ah"], PACK["nominal_v"], PACK["usable_fraction"]
    )
    night_wh = PACK["night_power_w"] * PACK["night_hours"]
    margin = pack_wh / night_wh
    return {
        "divider": divider,
        "currents_min": currents_min,
        "currents_nom": currents_nom,
        "linear_loss_w": linear_loss,
        "switching_loss_w": switching_loss,
        "charge_h": charge_h,
        "hot_c": hot_c,
        "cold_c": cold_c,
        "adc": adc,
        "surface_c": surface_c,
        "pack_wh": pack_wh,
        "night_wh": night_wh,
        "night_margin": margin,
    }


def checks(values: dict[str, object] | None = None) -> list[Check]:
    v = design_values() if values is None else values
    divider = v["divider"]
    currents = v["currents_min"]
    adc = v["adc"]
    result = [
        Check(
            "Sai số hồi tiếp boost",
            f"{divider.error_pct:.2f} %",
            "< 1,00 %",
            divider.error_pct < 1.0,
        ),
        Check(
            "Đỉnh dòng cuộn cảm @3,0 V",
            f"{_fmt(currents.peak_a, 2)} A",
            f"< Isat {BOOST['inductor_isat_a']:.1f} A (dư 20 %)",
            currents.peak_a <= BOOST["inductor_isat_a"] / 1.2,
        ),
        Check(
            "Đỉnh dòng dưới giới hạn chuyển mạch",
            f"{_fmt(currents.peak_a, 2)} A",
            f"< {BOOST['current_limit_a']:.2f} A",
            currents.peak_a < BOOST["current_limit_a"],
        ),
        Check(
            "Điện áp vào ADC khi pin đầy",
            f"{adc.adc_mv_at_max:.0f} mV",
            f"≤ {BATTERY_ADC['vadc_ref_v'] * 1000:.0f} mV",
            adc.adc_mv_at_max <= BATTERY_ADC["vadc_ref_v"] * 1000.0,
        ),
        Check(
            "Độ phân giải đo pin",
            f"{adc.mv_per_lsb:.2f} mV/LSB",
            f"≤ {BATTERY_ADC['max_mv_per_lsb']:.1f} mV/LSB",
            adc.mv_per_lsb <= BATTERY_ADC["max_mv_per_lsb"],
        ),
        Check(
            "Thời gian sạc 15 Ah nếu 1,5 A",
            f"{v['charge_h']:.1f} h",
            "< 12 h",
            v["charge_h"] < 12.0,
        ),
        Check(
            "Nhiệt mặt vỏ (không nắng), 45 °C",
            f"{v['surface_c']:.1f} °C",
            f"< {THERMAL['max_surface_c']:.0f} °C",
            v["surface_c"] < THERMAL["max_surface_c"],
        ),
        Check(
            "Dư pin kịch bản đêm, pack 15 Ah",
            f"{v['night_margin']:.2f}×",
            f"≥ {PACK['min_margin']:.2f}×",
            v["night_margin"] >= PACK["min_margin"],
        ),
    ]
    return result


def all_passed() -> bool:
    return all(check.passed for check in checks())
