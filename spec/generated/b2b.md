# J_B2B — pinout PWR ↔ CMP (sinh tự động)

- Nguồn: `spec/b2b.toml`
- Connector: **Box header 2x13, 2.54 mm, có khóa và chống cắm ngược**, 26 chân
- Mức logic: 3.3 V

| Chân | Tín hiệu | Hướng | Dòng tối đa (A) | Ghi chú |
|---|---|---|---|---|
| 1 | +5V_SOC | PWR->CMP | 1.0 | Rail SoC, 3 chân, tổng 3 A |
| 2 | +5V_MODEM | PWR->CMP | 1.0 | Rail modem, 3 chân. Đỉnh của modem Cat-1 lớn hơn bản nháp 0.6 A |
| 3 | +5V_SOC | PWR->CMP | 1.0 |  |
| 4 | +5V_MODEM | PWR->CMP | 1.0 |  |
| 5 | +5V_SOC | PWR->CMP | 1.0 |  |
| 6 | GND | - | 1.0 |  |
| 7 | GND | - | 1.0 |  |
| 8 | GND | - | 1.0 |  |
| 9 | +3V3 | PWR->CMP | 0.75 | Tham chiếu logic và cảm biến |
| 10 | GND | - | 1.0 |  |
| 11 | +3V3 | PWR->CMP | 0.75 |  |
| 12 | GND | - | 1.0 |  |
| 13 | I2C_SDA | bidir |  | trên PWR, 2.2 kOhm tới +3V3 |
| 14 | I2C_SCL | bidir |  | trên PWR, 2.2 kOhm tới +3V3 |
| 15 | MCU_IRQ | PWR->CMP |  | Open-drain, mức thấp là có sự kiện |
| 16 | SOC_READY | CMP->PWR |  | SoC báo đã khởi động xong |
| 17 | MODEM_PWRKEY | PWR->CMP |  | Từ MCU ra header modem |
| 18 | MODEM_RESET | PWR->CMP |  | Từ MCU ra header modem |
| 19 | MODEM_STATUS | CMP->PWR |  | Từ modem về MCU |
| 20 | USB_SEL | PWR->CMP |  | MCU chọn modem hoặc pad nạp dịch vụ (D-20/O-13) |
| 21 | MODEM_RI | CMP->PWR |  | Ring Indicator từ modem về MCU. Kênh đánh thức khi SoC tắt (docs/15 §4.2) |
| 22 | SPARE_SOC2 | CMP->PWR |  |  |
| 23 | +5V_MODEM | PWR->CMP | 1.0 |  |
| 24 | GND | - | 1.0 |  |
| 25 | GND | - | 1.0 |  |
| 26 | GND | - | 1.0 |  |

## Ngân sách dòng theo net

| Net | Số chân | Tổng dòng chân (A) | Yêu cầu thiết kế (A) | Dư | Đạt |
|---|---|---|---|---|---|
| +5V_SOC | 3 | 3.00 | 1.50 | 2.00× | có |
| +5V_MODEM | 3 | 3.00 | 1.80 | 1.67× | có |
| GND | 8 | 8.00 | 3.00 | 2.67× | có |
| +3V3 | 2 | 1.50 | 0.60 | 2.50× | có |

Tất cả net đạt hệ số dư tối thiểu 1.25×.

## Ghi chú thiết kế

- Đây là hợp đồng giữa hai board: đổi file này phải đổi cả PWR và CMP, và tăng phiên bản.
- Các chân dự phòng không được dùng cho chức năng bắt buộc.
- Cáp B2B phải ngắn; nếu dài quá 60 mm, cần kiểm tra lại I2C và dòng.
