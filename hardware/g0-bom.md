# BOM giai đoạn 0 — đo trên dev board

- Trạng thái: **chưa đặt hàng.** Giá là `[ƯỚC TÍNH]`, chưa có báo giá.
- Mục đích: mua đủ để làm G0 ([07](../docs/07-ke-hoach-phat-trien.md) §Giai đoạn 0), không mua cho sản phẩm.
- Quy tắc: mỗi dòng phải có MPN thật trước khi đặt; dòng nào chưa có MPN thì ghi "chưa chọn", không đặt theo tên chung.

## 1. Bắt buộc

| # | Hạng mục | MPN / loại đề xuất | SL | Giá (USD) | Phải xác minh trước khi đặt |
|---|---|---|---|---|---|
| 1 | SoC dev board | Luckfox Pico Max (RV1106G3, 256 MB) | 2 | 15–30 | Có camera CSI và USB host |
| 2 | Module cho sản phẩm | Luckfox Core1106D1408 (eMMC 8 GB) | 3 | 15–25 | Còn hàng, có bản vẽ chân 112 pin |
| 3 | Breakout modem | EC200U-EU breakout có USB + SIM + u.FL | 2 | 15–35 | Có chân **RI** ra header; hạ áp 5→3,8 V ≥1,8 A |
| 4 | Camera module | SC3336 FPC 20 chân, có IR-CUT + LED IR | 2 | 8–18 | Pinout FPC; độ dài cáp; áp 3,3 V hay 1,8 V |
| 5 | Pack LFP 10 Ah có BMS | Nhà cung cấp nội địa | 1 | 25–45 | UN38.3, NTC, BMS ≤100 µA, sạc ≥1,5 A |
| 6 | Pack LFP 15 Ah có BMS | Nhà cung cấp nội địa | 1 | 40–75 | Như trên; đây là cấu hình chốt (D-18) |
| 7 | SIM dữ liệu 3 mạng | Viettel / Vinaphone / MobiFone | 3 | 5–15 | Có eDRX/PSM, hỏi nhà mạng |
| 8 | Ăng-ten LTE | u.FL, 700–2600 MHz | 3 | 3–8 | Hệ số tăng ích, cáp |
| 9 | Nguồn bench | 0–30 V, 5 A, có giới hạn dòng | 1 | 80–150 | Đủ để mô phỏng pin 3,0–3,65 V |
| 10 | Máy đo dòng | Nordic PPK2 hoặc tương đương | 1 | 100–150 | Đo được µA tới A |
| 11 | Đồng hồ vạn năng | 4½ chữ số | 1 | 50–100 | Đo mV chính xác |
| 12 | Shunt đo đỉnh modem | 0,01 Ω 1 % 2 W + mạch khuếch đại | 2 | 5–15 | Hoặc dùng đầu dò dòng của scope |
| 13 | Tản nhiệt tạm | Miếng dẫn nhiệt 20×20 mm, nhôm | 5 | 5–10 | Độ dày phù hợp khe hở |
| 14 | Connector, dây, đầu đo | B2B 2×13, JST, dây 20 AWG | — | 20–40 | Đúng dòng ≥3 A cho đường 5 V |

Tổng `[ƯỚC TÍNH]`: **380–720 USD**, chưa gồm oscilloscope và tủ sấy.

## 2. Nên mượn, không nên mua

| Hạng mục | Vì sao |
|---|---|
| Oscilloscope ≥100 MHz, 2 kênh | Chỉ dùng cho M-08, M-19, M-36; mua mới 300–800 USD |
| Tủ sấy 60–80 °C | Dùng cho M-05, M-22, M-38; mượn phòng lab |
| Cân tiểu ly | Cân pack, tính năng lượng riêng |

## 3. Trước khi đặt: kiểm ba câu

1. Breakout modem có đưa **RI** ra header không? Nếu không, kênh Watch không chạy được (D-17).
2. Pack có BMS **≤100 µA** và cho sạc **≥1,5 A** không? Nếu không, đổi nhà cung cấp (NFR-04, D-23).
3. Core1106D có phải bản **eMMC** không? Bản NAND 256 MB không đủ OTA A/B (D-19).

## 4. Sau khi nhận: việc đầu tiên

1. Chụp ảnh, cân, đo kích thước từng món; ghi vào sổ đo.
2. Đo tự tiêu BMS bằng PPK2 trước khi lắp (M-37).
3. In datasheet và bản vẽ chân của camera, breakout, module; đánh dấu chân nào đã xác minh.
4. Chỉ sau đó mới bắt đầu G0.
