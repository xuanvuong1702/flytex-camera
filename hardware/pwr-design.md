# Thiết kế PWR Rev A — giá trị tính toán

- **File sinh tự động** từ `hardware/calc/design.py`; không sửa tay.
- Kiểm tra: `python -m hardware.calc.cli --check` (CI chạy lệnh này).
- Mọi giá trị là **tính toán từ tham số thiết kế**, không phải số đo. Chưa có board nào được đặt.

## 1. Cấu hình chốt

| Hạng mục | Chọn | Ghi chú |
|---|---|---|
| Boost 5 V | TPS61088 | 3.0 A, 597 kHz, cuộn 1.2 µH |
| Buck 3,3 V | TPS62840 | 0.75 A; Vref **chưa xác minh** |
| Sạc | tuyen tinh LFP BQ25070, float 3,5 V, power-path, 935 mA (11 xung) | 0.9 A, 5 V vào |
| Pack | LFP 1S 15 Ah | 48 Wh danh định |

## 2. Boost 5 V

### 2.1 Hồi tiếp

- Vout đặt: 5.00 V, Vref 1.204 V `[CHƯA XÁC MINH]`
- Cặp E96 chọn: **R_top = 169.0 kΩ**, **R_bottom = 53.6 kΩ**
- Vout thực: 5.000 V, sai số 0.00 %

### 2.2 Dòng điện

| Điều kiện | D | I vào | I cuộn (trung bình) | Gợn | Đỉnh |
|---|---|---|---|---|---|
| 3.0 V (pin yếu) | 0.460 | 5.56 A | 5.56 A | 1.93 A | 6.52 A |
| 3.2 V (danh định) | 0.424 | 5.21 A | 5.21 A | 1.89 A | 6.16 A |

Cuộn cảm chọn: 1.2 µH, Isat ≥ 9 A. Giới hạn dòng theo Rilim: 8.47 A `[CHƯA XÁC MINH]`.

## 3. Sạc pin

**Đã chọn BQ25070**: sạc tuyến tính LFP 1S, float 3,5 V cố định, power-path, NTC, standalone. Dòng sạc đặt bằng **11 xung trên CTRL = 935 mA** (không phải điện trở); mặc định không gửi xung chỉ 285 mA. Đổi từ BQ25798 vì BQ25798 mặc định 1S 4,2 V.

| Tuyến tính BQ25070 (chốt) | 1.40 W | (5 − 3,5) × 0,935; IC có thermal regulation, vẫn phải đo trong vỏ |

Thời gian sạc 15 Ah từ 20 % ở 0.9 A: **12.8 giờ** (hiệu suất 100 %).

## 4. Cắt sạc theo nhiệt (NTC trên pack)

BQ25070: V_TS = 12,5 % VLDO khi nóng, 25 % khi lạnh; NTC 10 kΩ B3950 song song R2. Chọn **R1 = 20.00 kΩ** (LDO→TS), **R2 = 8.25 kΩ** (TS→GND): cắt nóng **44.9 °C**, cắt lạnh **-0.6 °C**. Đo lại bằng tủ sấy (M-05).

## 5. Đo điện áp pin

Chia áp 100 kΩ / 100 kΩ, ADC 12 bit, Vref 3.3 V.

- Tỉ lệ chia: 2.00×
- Điện áp vào ADC khi pin 3,65 V: **1825 mV** (còn dư 1475 mV)
- Độ phân giải quy về pin: **1.61 mV/LSB**

## 6. Nhiệt (xấp xỉ, chưa đo)

Vỏ 0.0372 m², hệ số tản 8.0 W/m²·K, tổn hao 3.8 W, môi trường 45 °C.

- Tăng nhiệt: **12.8 K**
- Nhiệt mặt vỏ: **57.8 °C** (chưa tính nắng chiếu trực tiếp)

## 7. Năng lượng kịch bản đêm

Pack 15 Ah × 3.2 V × 85 % = **40.8 Wh dùng được**.
Kịch bản đêm 3.8 W trong 7 h cần 26.6 Wh → hệ số dư **1.53×**.

## 8. Kiểm tra tự động

| Kiểm tra | Giá trị | Giới hạn | Kết quả |
|---|---|---|---|
| Sai số hồi tiếp boost | 0.00 % | < 1,00 % | ĐẠT |
| Đỉnh dòng cuộn cảm @3,0 V | 6.52 A | < Isat 9.0 A (dư 20 %) | ĐẠT |
| Đỉnh dòng dưới giới hạn chuyển mạch | 6.52 A | < 8.47 A | ĐẠT |
| Điện áp vào ADC khi pin đầy | 1825 mV | ≤ 3300 mV | ĐẠT |
| Độ phân giải đo pin | 1.61 mV/LSB | ≤ 5.0 mV/LSB | ĐẠT |
| Ngưỡng nóng NTC (TS) | 44.9 °C | 43–47 °C | ĐẠT |
| Ngưỡng lạnh NTC (TS) | -0.6 °C | -3–3 °C | ĐẠT |
| Thời gian sạc 15 Ah ở 935 mA | 12.8 h | < 14 h | ĐẠT |
| Nhiệt mặt vỏ (không nắng), 45 °C | 57.8 °C | < 60 °C | ĐẠT |
| Dư pin kịch bản đêm, pack 15 Ah | 1.53× | ≥ 1.30× | ĐẠT |

Tất cả kiểm tra đạt.

## 9. Điểm chưa xác minh

1. Vref, tần số chuyển mạch và giới hạn dòng của TPS61088 phải đối chiếu datasheet.
2. Vref của TPS62840 chưa chọn; không tính được mạch hồi tiếp 3,3 V.
3. Dòng sạc 935 mA và mạng NTC đã tính; vẫn phải đo M-05 và kiểm tồn kho BQ25070.
4. Hệ số tản nhiệt 8 W/m²·K là giả định; nắng chiếu trực tiếp chưa tính.
5. Không có số đo dòng, nhiệt hay thời gian chạy thật.
