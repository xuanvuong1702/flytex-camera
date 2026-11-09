# 03 — Giao diện

- Trạng thái: **v1.1**, cập nhật 2026-11-09 theo [13](13-tinh-kha-thi.md)
- Đây là **hợp đồng** giữa các board. Số liệu nguồn nằm trong [spec/b2b.toml](../spec/b2b.toml) và [spec/registers.toml](../spec/registers.toml); bảng dưới đây sinh từ đó. Đổi hợp đồng phải sửa spec, chạy `python spec/generate.py`, rồi cập nhật cả hai phía.
- Lịch sử: bản v0.1 giữ ở git. Những gì đã đổi so với v0.1 ghi ở §7.

## 1. Rail nguồn

| Rail | Nguồn | Điện áp | Dòng thiết kế | Ghi chú |
|---|---|---|---|---|
| VBAT | Pack qua BMS | 3,0–3,65 V | đỉnh ~5,6 A tại 3,0 V | Chỉ có trên PWR |
| +5V_BOOST | Boost | 5,0 V | 3 A (giới hạn boost) | Chỉ có trên PWR |
| +5V_SOC | Công tắc tải | 5,0 V | 1,5 A | Sang CMP, 3 chân B2B |
| +5V_MODEM | Công tắc tải | 5,0 V | 1,8 A | Sang CMP rồi tới header modem, 3 chân B2B |
| +3V3 | Buck | **3,0–3,3 V** (bám pin khi pin yếu, không phải 3,3 V cố định) | 0,6 A | MCU, cảm biến, tham chiếu logic |

**Thay đổi so với v0.1:** `+5V_MODEM` từ "0,5–0,6 A, 2 chân" lên 1,8 A, 3 chân. Lý do: đỉnh dòng của modem Cat-1 lớn hơn con số cũ và boost 3 A phải chia cho cả SoC; xem [13](13-tinh-kha-thi.md) F-03. Con số 1,8 A là cận trên thiết kế, phải thay bằng phép đo (M-10).

Kiểm tra tự động: `spec/generated/b2b.md` §"Ngân sách dòng theo net" báo hệ số dư của từng net; dưới 1,25× là không được đặt board.

## 2. Connector ngoài của PWR

| Connector | Tín hiệu | Ghi chú |
|---|---|---|
| J_USBC | VBUS, GND, CC1, CC2 | Chỉ nguồn. D+/D− không nối `[ĐỀ XUẤT]` |
| J_PACK | BAT+, BAT− | Hai chân công suất ≥ 10 A, có khóa chống cắm ngược |
| J_NTC | NTC, GND | Dây NTC từ pack |
| J_SENS | +3V3, PIR_OUT, GND, +3V3, DQ (1-Wire), GND | PIR và hai cảm biến nhiệt DS18B20 trên cùng một bus |
| J_MEAS | 2 chân nối tiếp VBAT | Cắm máy đo dòng, mặc định có jumper |
| J_SWD | SWDIO, SWCLK, NRST, GND (+3V3 tùy chọn) | Nạp và gỡ lỗi MCU |

## 3. Connector giữa PWR và CMP (J_B2B)

**Chốt:** 2×13, 2,54 mm, 26 chân, mức logic 3,3 V. **PWR dùng header đực TSM-113-01-L-DV; CMP dùng socket cái SSM-113-L-DV**; cắt chân 26 làm khóa chống cắm ngược (D-24). Bảng chân đầy đủ và ngân sách dòng: [spec/generated/b2b.md](../spec/generated/b2b.md). File CSV để nhập vào EDA: [spec/generated/pinout_pwr_cmp.csv](../spec/generated/pinout_pwr_cmp.csv).

Tóm tắt tín hiệu bắt buộc:

| Nhóm | Tín hiệu | Số chân |
|---|---|---|
| Nguồn | +5V_SOC, +5V_MODEM, +3V3 | 3 + 3 + 2 |
| Đất | GND | 8 |
| Bus | I2C_SCL, I2C_SDA | 2 |
| Điều khiển | MCU_IRQ, SOC_READY, **MODEM_RI** | 3 |
| Modem | MODEM_PWRKEY, MODEM_RESET, MODEM_STATUS | 3 |
| Dự phòng | SPARE_SOC2 | 1 |

**Thay đổi so với v0.1:** thêm `MODEM_RI` (chân 21) để kênh đánh thức SMS hoạt động khi SoC tắt ([15](15-giao-thuc-va-cloud.md) §4.2); đổi một chân dự phòng MCU lấy chân này. Số chân dự phòng còn 2; sau đó D-22 dùng chân 20 cho `USB_SEL`, còn 1.

## 4. Connector trên CMP

| Connector | Tín hiệu | Ghi chú |
|---|---|---|
| J_CAM | FPC 20 chân của module camera | **Pinout chưa xác minh**: lấy từ datasheet của module được chọn (O-02) |
| J_MODEM | +5V_MODEM, GND, USB_DP, USB_DM, UART_TX, UART_RX, PWRKEY, STATUS, RESET, **RI** | Khớp breakout được chọn (O-04) |
| J_SD | microSD | Phải tiếp cận được khi mở vỏ, vì có thể là đường nạp dự phòng |
| J_CON | UART console 3 chân: TX, RX, GND | Gỡ lỗi SoC |
| J_SVC | Pad USB_DP/DM + GND + VBUS cảm biến | **Mới:** đường nạp dịch vụ, xem §7 và [13](13-tinh-kha-thi.md) F-01 |

### 4.1 Một cổng USB, hai mục đích

Core1106 chỉ có **một** cổng USB 2.0 Host/Device `[ĐÃ XÁC MINH]`. Bản nháp dùng nó cho modem và không nói gì về nạp firmware. Ba phương án, chốt ở G0:

| Phương án | Ưu | Nhược | Chọn |
|---|---|---|---|
| A. Mux USB 2.0 hai kênh (GPIO điều khiển) | Nạp được tại hiện trường | Thêm linh kiện, thêm 2 chân điều khiển | **Đề xuất** |
| B. Nạp qua thẻ SD | Không thêm linh kiện | Phải mở vỏ; phụ thuộc bootloader | Dự phòng |
| C. Chỉ nạp trên bàn, tháo modem | Đơn giản cho prototype | Không cứu được thiết bị ở hiện trường | Chỉ prototype |

Phương án A cần `USB_SEL`. **Đã bổ sung ở chân 20** (D-22, 2026-11-09), do MCU điều khiển; mux cụ thể vẫn mở ở O-13. Chân dự phòng còn lại là `SPARE_SOC2`.

## 5. Giao thức MCU ↔ SoC

**Đã chuyển sang [15](15-giao-thuc-va-cloud.md) §2.** Bảng thanh ghi sinh tự động ở [spec/generated/regmap.md](../spec/generated/regmap.md). Không chép lại bảng ở đây để tránh hai nguồn sự thật.

Tóm tắt những gì đổi so với bản nháp v0.1:

| Nội dung | v0.1 | v1.1 |
|---|---|---|
| Thứ tự byte | `WAKE_IN_S` little-endian, `VBAT_MV` cao trước | **Tất cả big-endian**, đọc byte cao chốt, ghi byte cuối commit |
| Thanh ghi mới | — | `SYS_FLAGS`, `WAKE_CHAN`, `WAKE_PERIOD_S`, `UPTIME_S`, `BOOT_COUNT` |
| Mã lệnh | 4 mã | thêm `MODEM_RESET`, `CLEAR_FAULT`, `MODEM_PWRKEY` |
| Bit sự kiện | 6 bit | thêm `WAKE_ALARM`, `BUTTON` |
| Phiên bản | 0x01 (nháp) | **1.1** (0x11) |

## 6. Giao diện cơ khí

- Hình dạng board và lỗ bắt vít chốt cùng lúc với vỏ ([06](06-co-khi-nhiet.md)).
- Vị trí tản nhiệt SoC chốt sớm, vì vỏ nhôm là đường tản nhiệt chính.
- Vùng cấm cho ăng-ten quanh u.FL.

## 7. Nhật ký thay đổi v1.1

| Ngày | Thay đổi | Lý do |
|---|---|---|
| 2026-11-09 | `+5V_MODEM` 1,8 A, 3 chân | F-03: boost 3 A không đủ cho SoC + đỉnh modem |
| 2026-11-09 | Thêm `MODEM_RI` chân 21 | F-02: kênh đánh thức khi SoC tắt |
| 2026-11-09 | Thêm `J_SVC` pad nạp | F-01: một cổng USB |
| 2026-11-09 | Regmap big-endian, thêm thanh ghi | Sửa mâu thuẫn nội tại, thêm kênh đánh thức |
| 2026-11-09 | Tham chiếu spec thay vì bảng chép tay | Nguyên tắc "mỗi con số một nguồn" |
