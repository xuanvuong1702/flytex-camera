"""Sinh báo cáo thiết kế PWR từ các phép tính trong `design.py`."""

from __future__ import annotations

from . import design, pwr


def render() -> str:
    BOOST = design.BOOST
    BUCK = design.BUCK
    CHARGER = design.CHARGER
    NTC = design.NTC
    BATTERY_ADC = design.BATTERY_ADC
    THERMAL = design.THERMAL
    PACK = design.PACK
    v = design.design_values()
    divider = v["divider"]
    currents_min = v["currents_min"]
    currents_nom = v["currents_nom"]
    adc = v["adc"]
    rows = design.checks(v)

    out: list[str] = []
    w = out.append
    w("# Thiết kế PWR Rev A — giá trị tính toán")
    w("")
    w("- **File sinh tự động** từ `hardware/calc/design.py`; không sửa tay.")
    w("- Kiểm tra: `python -m hardware.calc.cli --check` (CI chạy lệnh này).")
    w("- Mọi giá trị là **tính toán từ tham số thiết kế**, không phải số đo. "
      "Chưa có board nào được đặt.")
    w("")
    w("## 1. Cấu hình chốt")
    w("")
    w("| Hạng mục | Chọn | Ghi chú |")
    w("|---|---|---|")
    w(f"| Boost 5 V | {BOOST['ic']} | {BOOST['iout_max_a']:.1f} A, "
      f"{BOOST['fsw_hz'] / 1000:.0f} kHz, cuộn {BOOST['inductance_h'] * 1e6:.1f} µH |")
    w(f"| Buck 3,3 V | {BUCK['ic']} | {BUCK['iout_max_a']:.2f} A; "
      f"Vref **chưa xác minh** |")
    w(f"| Sạc | {CHARGER['topology']} | {CHARGER['current_a']:.1f} A, "
      f"{CHARGER['vbus_v']:.0f} V vào |")
    w(f"| Pack | LFP 1S {PACK['capacity_ah']:.0f} Ah | "
      f"{pwr.pack_wh(PACK['capacity_ah'], PACK['nominal_v']):.0f} Wh danh định |")
    w("")
    w("## 2. Boost 5 V")
    w("")
    w("### 2.1 Hồi tiếp")
    w("")
    w(f"- Vout đặt: {BOOST['vout_v']:.2f} V, Vref {BOOST['vref_v']:.3f} V "
      f"`[CHƯA XÁC MINH]`")
    w(f"- Cặp E96 chọn: **R_top = {divider.top_ohm / 1000:.1f} kΩ**, "
      f"**R_bottom = {divider.bottom_ohm / 1000:.1f} kΩ**")
    w(f"- Vout thực: {divider.vout_v:.3f} V, sai số {divider.error_pct:.2f} %")
    w("")
    w("### 2.2 Dòng điện")
    w("")
    w("| Điều kiện | D | I vào | I cuộn (trung bình) | Gợn | Đỉnh |")
    w("|---|---|---|---|---|---|")
    for label, current in (
        (f"{BOOST['vin_min_v']:.1f} V (pin yếu)", currents_min),
        (f"{BOOST['vin_nom_v']:.1f} V (danh định)", currents_nom),
    ):
        w(f"| {label} | {current.duty:.3f} | {current.input_a:.2f} A | "
          f"{current.inductor_avg_a:.2f} A | {current.ripple_pp_a:.2f} A | "
          f"{current.peak_a:.2f} A |")
    w("")
    w(f"Cuộn cảm chọn: {BOOST['inductance_h'] * 1e6:.1f} µH, "
      f"Isat ≥ {BOOST['inductor_isat_a']:.0f} A. Giới hạn dòng theo Rilim: "
      f"{BOOST['current_limit_a']:.2f} A `[CHƯA XÁC MINH]`.")
    w("")
    w("## 3. Sạc pin")
    w("")
    w("| Phương án | Tổn hao ở 1,5 A | Ghi chú |")
    w("|---|---|---|")
    w(f"| Tuyến tính (bản nháp) | {v['linear_loss_w']:.2f} W | "
      f"(5 − 3,6) × 1,5; trong vỏ kín là bài toán nhiệt |")
    w(f"| Xung, hiệu suất 90 % | {v['switching_loss_w']:.2f} W | D-16 chốt dùng loại này |")
    w("")
    w(f"Thời gian sạc {CHARGER['capacity_ah']:.0f} Ah từ "
      f"{CHARGER['soc_start'] * 100:.0f} % ở {CHARGER['current_a']:.1f} A: "
      f"**{v['charge_h']:.1f} giờ** (hiệu suất {CHARGER['efficiency'] * 100:.0f} %).")
    w("")
    w("## 4. Cắt sạc theo nhiệt (NTC trên pack)")
    w("")
    w(f"NTC {NTC['r25_ohm'] / 1000:.0f} kΩ B{NTC['beta']:.0f}, "
      f"kéo lên bằng {NTC['r_pull_ohm'] / 1000:.2f} kΩ; ngưỡng chip "
      f"{NTC['threshold_hot_ratio'] * 100:.1f}–{NTC['threshold_cold_ratio'] * 100:.1f} % VIN.")
    w("")
    w("| Nhiệt độ | R_NTC | Tỉ lệ V_TEMP/VIN |")
    w("|---|---|---|")
    for temp in (0.0, 10.0, 25.0, 35.0, 40.0, 45.0, 60.0):
        r_ntc = pwr.ntc_resistance_ohm(temp, NTC["r25_ohm"], NTC["beta"])
        ratio = pwr.ntc_ratio(temp, NTC["r25_ohm"], NTC["beta"], NTC["r_pull_ohm"])
        w(f"| {temp:.0f} °C | {r_ntc / 1000:.2f} kΩ | {ratio * 100:.1f} % |")
    w("")
    w(f"Điểm cắt nóng: **{v['hot_c']:.1f} °C**; điểm cắt lạnh: "
      f"**{v['cold_c']:.1f} °C**. Không phải đúng 40 °C vì ngưỡng chip có dải; "
      f"đo thật ở M-05.")
    w("")
    w("## 5. Đo điện áp pin")
    w("")
    w(f"Chia áp {BATTERY_ADC['r_top_ohm'] / 1000:.0f} kΩ / "
      f"{BATTERY_ADC['r_bottom_ohm'] / 1000:.0f} kΩ, ADC "
      f"{BATTERY_ADC['bits']} bit, Vref {BATTERY_ADC['vadc_ref_v']:.1f} V.")
    w("")
    w(f"- Tỉ lệ chia: {adc.divider_ratio:.2f}×")
    w(f"- Điện áp vào ADC khi pin 3,65 V: **{adc.adc_mv_at_max:.0f} mV** "
      f"(còn dư {adc.headroom_v * 1000:.0f} mV)")
    w(f"- Độ phân giải quy về pin: **{adc.mv_per_lsb:.2f} mV/LSB**")
    w("")
    w("## 6. Nhiệt (xấp xỉ, chưa đo)")
    w("")
    w(f"Vỏ {THERMAL['area_m2']:.4f} m², hệ số tản {THERMAL['h_w_m2k']:.1f} W/m²·K, "
      f"tổn hao {THERMAL['dissipation_w']:.1f} W, môi trường "
      f"{THERMAL['ambient_c']:.0f} °C.")
    w("")
    w(f"- Tăng nhiệt: **{v['surface_c'] - THERMAL['ambient_c']:.1f} K**")
    w(f"- Nhiệt mặt vỏ: **{v['surface_c']:.1f} °C** (chưa tính nắng chiếu trực tiếp)")
    w("")
    w("## 7. Năng lượng kịch bản đêm")
    w("")
    w(f"Pack {PACK['capacity_ah']:.0f} Ah × {PACK['nominal_v']:.1f} V × "
      f"{PACK['usable_fraction'] * 100:.0f} % = **{v['pack_wh']:.1f} Wh dùng được**.")
    w(f"Kịch bản đêm {PACK['night_power_w']:.1f} W trong {PACK['night_hours']:.0f} h "
      f"cần {v['night_wh']:.1f} Wh → hệ số dư **{v['night_margin']:.2f}×**.")
    w("")
    w("## 8. Kiểm tra tự động")
    w("")
    w("| Kiểm tra | Giá trị | Giới hạn | Kết quả |")
    w("|---|---|---|---|")
    for check in rows:
        w(f"| {check.name} | {check.value} | {check.limit} | "
          f"{'ĐẠT' if check.passed else '**KHÔNG ĐẠT**'} |")
    w("")
    failed = [check for check in rows if not check.passed]
    if failed:
        w(f"> **Có {len(failed)} kiểm tra không đạt. Không được đặt board trước khi sửa.**")
    else:
        w("Tất cả kiểm tra đạt.")
    w("")
    w("## 9. Điểm chưa xác minh")
    w("")
    w("1. Vref, tần số chuyển mạch và giới hạn dòng của TPS61088 phải đối chiếu datasheet.")
    w("2. Vref của TPS62840 chưa chọn; không tính được mạch hồi tiếp 3,3 V.")
    w("3. Chưa chọn IC sạc xung cụ thể (O-05); tổn hao chỉ là ước lượng theo hiệu suất.")
    w("4. Hệ số tản nhiệt 8 W/m²·K là giả định; nắng chiếu trực tiếp chưa tính.")
    w("5. Không có số đo dòng, nhiệt hay thời gian chạy thật.")
    return "\n".join(out) + "\n"
