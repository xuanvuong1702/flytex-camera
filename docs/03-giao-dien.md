# 03 — Giao diện

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09
- Đây là **hợp đồng** giữa các board. Đổi tài liệu này phải đi kèm đổi cả hai phía và tăng phiên bản.

## 1. Rail nguồn

| Rail | Nguồn | Điện áp | Dòng tối đa | Ghi chú |
|---|---|---|---|---|
| VBAT | Pack qua BMS | 3,0–3,65 V | đỉnh khoảng 5,6 A tại 3,0 V | Chỉ có trên PWR |
| +5V_BOOST | Boost | 5,0 V | 3 A | Chỉ có trên PWR |
| +5V_SOC | Công tắc tải | 5,0 V | theo ngân sách SoC | Sang CMP |
| +5V_MODEM | Công tắc tải | 5,0 V | đỉnh khoảng 0,5–0,6 A | Sang CMP rồi tới header modem |
| +3V3 | Buck | 3,3 V | 0,75 A | MCU, cảm biến, tham chiếu logic |

Các con số dòng là `[KẾ THỪA]` `[ƯỚC TÍNH]`.

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

Số chân cuối cùng và loại connector chốt khi vẽ schematic; danh sách dưới là tín hiệu bắt buộc. Mức logic 3,3 V.

| Tín hiệu | Hướng | Mô tả |
|---|---|---|
| +5V_SOC | PWR → CMP | ≥ 3 chân |
| +5V_MODEM | PWR → CMP | ≥ 2 chân |
| +3V3 | PWR → CMP | ≥ 2 chân |
| GND | — | ≥ 6 chân, rải đều |
| I2C_SCL, I2C_SDA | MCU slave ↔ SoC master | Pull-up đặt trên PWR |
| MCU_IRQ | PWR → CMP | Mức thấp là có sự kiện, open-drain |
| SOC_READY | CMP → PWR | SoC báo đã khởi động xong |
| MODEM_PWRKEY | PWR → CMP | Từ MCU, ra header modem |
| MODEM_RESET | PWR → CMP | Từ MCU, ra header modem |
| MODEM_STATUS | CMP → PWR | Từ modem, MCU đọc |
| SPARE_MCU[1..2] | tùy chọn | Dự phòng, nối tới GPIO MCU |
| SPARE_SOC[1..2] | tùy chọn | Dự phòng, nối tới GPIO SoC |

## 4. Connector trên CMP

| Connector | Tín hiệu | Ghi chú |
|---|---|---|
| J_CAM | FPC 20 chân của module camera | **Pinout chưa xác minh**: lấy từ datasheet của module camera được chọn (O-02) |
| J_MODEM | +5V_MODEM, GND, USB_DP, USB_DM, UART_TX, UART_RX, PWRKEY, STATUS, RESET | Khớp với breakout được chọn (O-04); chọn breakout đưa ra cả USB |
| J_SD | microSD | |
| J_CON | UART console 3 chân: TX, RX, GND | Gỡ lỗi SoC |
| Pad nạp SoC | Theo module Core1106 | Nạp qua thẻ SD hoặc pad USB riêng `[CHƯA XÁC MINH]` |

## 5. Giao thức MCU ↔ SoC (dự thảo v0.1)

I2C, MCU là slave, địa chỉ 7 bit `0x30` `[KẾ THỪA]`, tốc độ 100 kHz mặc định, nâng lên sau khi đo.

Quy tắc:

1. SoC luôn đọc `PROTO_VER` trước và từ chối làm việc nếu phiên bản chính khác nhau.
2. Phiên bản phụ chỉ được **thêm** thanh ghi, không đổi nghĩa thanh ghi cũ.
3. Thanh ghi nhiều byte: đọc byte cao chốt (latch) byte thấp, để không đọc lệch.
4. Thanh ghi sự kiện xóa khi đọc.
5. MCU kéo `MCU_IRQ` xuống khi có sự kiện chưa được đọc; SoC không polling.

| Địa chỉ | Tên | R/W | Mô tả |
|---|---|---|---|
| 0x00 | PROTO_VER | R | [7:4] chính, [3:0] phụ. Dự thảo này là 0x01 |
| 0x01 | FW_VER | R | Phiên bản firmware MCU |
| 0x02 | STATUS | R | bit0 SOC_READY, bit1 SOC_POWER_ON, bit2 MODEM_POWER_ON, bit3 FAULT, bit4 LOW_BATT, bit5 VBUS_PRESENT |
| 0x03 | CHG | R | bit0 CHARGING, bit1 CHARGE_DONE, bit2 CHARGE_INHIBIT. Nghĩa chính xác theo chip sạc được chọn |
| 0x04 | EVENT | R, xóa khi đọc | bit0 PIR, bit1 SCHEDULE, bit2 VBUS_CHANGE, bit3 LOW_BATT, bit4 MODEM_STATUS, bit5 SHUTDOWN_REQ |
| 0x05 | FAULT_CODE | R | 0 là không lỗi; mã lỗi đặt sau |
| 0x06–0x07 | VBAT_MV | R | Cao rồi thấp; đọc 0x06 chốt 0x07 |
| 0x08 | BAT_TEMP_C | R | int8, 0x80 là không hợp lệ |
| 0x09 | AMB_TEMP_C | R | int8, 0x80 là không hợp lệ |
| 0x0A | CMD | W | 1 SOC_WAKE, 2 SOC_SHUTDOWN_DONE, 3 MODEM_ON, 4 MODEM_OFF; mã khác bị bỏ qua và ghi vào FAULT_CODE |
| 0x0B | MODE | R/W | 0 Eco, 1 Watch |
| 0x0C–0x0F | WAKE_IN_S | R/W | Số giây tới lần thức theo lịch, uint32 little-endian; ghi byte 0x0C chốt khi ghi 0x0F; 0 là tắt |
| 0x10 | EVENT_MASK | R/W | Bit nào bật thì mới kéo `MCU_IRQ` |

Bắt tay tắt máy an toàn: MCU đặt `SHUTDOWN_REQ` và kéo `MCU_IRQ` → SoC đóng file, đồng bộ SD, ghi `CMD = SOC_SHUTDOWN_DONE` → MCU cắt `+5V_SOC` sau thời gian chờ ngắn. Nếu SoC không trả lời trong thời gian cho phép (TBD, đo sau), MCU cắt cưỡng bức. Hiện thực ở [04](04-firmware.md).

## 6. Giao diện cơ khí

- Hình dạng board và lỗ bắt vít chốt cùng lúc với vỏ ([06](06-co-khi-nhiet.md)).
- Vị trí tản nhiệt SoC chốt sớm, vì vỏ nhôm là đường tản nhiệt chính.
- Vùng cấm cho ăng-ten quanh u.FL.
