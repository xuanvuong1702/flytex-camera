# Regmap MCU ↔ SoC (sinh tự động)

- Nguồn: `spec/registers.toml`
- Địa chỉ I2C 7 bit: `0x30`
- Phiên bản giao thức: **1.1**
- Số byte vùng thanh ghi: `0x18`

## 1. Thanh ghi

| Địa chỉ | Tên | R/W | Byte | Reset | Mô tả |
|---|---|---|---|---|---|
| 0x00 | PROTO_VER | R | 1 | 0x11 | Phiên bản giao thức: [7:4] chính, [3:0] phụ. SoC phải từ chối làm việc nếu khác major. |
| 0x01 | FW_VER | R | 1 | 0x10 | Phiên bản firmware MCU: [7:4] chính, [3:0] phụ. |
| 0x02 | STATUS | R | 1 | 0x00 | Trạng thái nguồn và hệ thống. |
| 0x03 | CHG | R | 1 | 0x00 | Trạng thái bộ sạc. Nghĩa bit phụ thuộc chip sạc được chọn. |
| 0x04 | EVENT | R | 1 | 0x00 | Bit sự kiện. Xóa khi đọc: mỗi lần đọc trả về các bit đã đặt rồi xóa. |
| 0x05 | FAULT_CODE | R | 1 | 0x00 | 0 là không lỗi. Mã lỗi xem bảng values. |
| 0x06–0x07 | VBAT_MV | R | 2 | 0x00 | Điện áp pin, 0..65535 mV. Đọc 0x06 chốt giá trị, 0x07 trả byte thấp. |
| 0x08 | BAT_TEMP_C | R | 1 | 0x80 | Nhiệt độ pin (NTC trên pack). 0x80 = không hợp lệ, không được trả giá trị giả. |
| 0x09 | AMB_TEMP_C | R | 1 | 0x80 | Nhiệt độ môi trường từ DS18B20. 0x80 = không hợp lệ. |
| 0x0A | CMD | W | 1 | 0x00 | Lệnh từ SoC. Mã lạ bị bỏ qua và đặt FAULT_CODE = BAD_CMD. |
| 0x0B | MODE | R/W | 1 | 0x00 | Chế độ ngủ đã cấu hình. 0 = Eco, 1 = Watch. |
| 0x0C–0x0F | WAKE_IN_S | R/W | 4 | 0x00 | Số giây tới lần thức theo lịch. Ghi từ 0x0C tới 0x0F, byte 0x0F kích hoạt. 0 là tắt. |
| 0x10 | EVENT_MASK | R/W | 1 | 0x3F | Bit nào bật thì MCU mới kéo MCU_IRQ cho sự kiện tương ứng. Cùng thứ tự bit với EVENT. |
| 0x11 | SYS_FLAGS | R | 1 | 0x02 | Nguyên nhân khởi động lại gần nhất (v1.1). |
| 0x12 | WAKE_CHAN | R/W | 1 | 0x00 | Kênh đánh thức khi SoC tắt (v1.1). Xem docs/15 §4. |
| 0x13–0x14 | WAKE_PERIOD_S | R/W | 2 | 0x00 | Chu kỳ hỏi của kênh đánh thức (v1.1). 0 là dùng giá trị mặc định của firmware. |
| 0x15–0x16 | UPTIME_S | R | 2 | 0x00 | Thời gian từ lúc MCU khởi động, bão hòa ở 65535 (v1.1). |
| 0x17 | BOOT_COUNT | R | 1 | 0x00 | Số lần khởi động lại đã đếm, lưu trong NVM, bão hòa ở 255 (v1.1). |

## 2. Bitfield

### STATUS

| Bit | Tên | Mô tả |
|---|---|---|
| 0 | SOC_READY | SoC đã bật và chạm SOC_READY |
| 1 | SOC_POWER_ON | Rail +5V_SOC đang bật |
| 2 | MODEM_POWER_ON | Rail +5V_MODEM đang bật |
| 3 | FAULT | Có lỗi đang hoạt động, xem FAULT_CODE |
| 4 | LOW_BATT | Pin dưới ngưỡng cảnh báo (có tải) |
| 5 | VBUS_PRESENT | Có nguồn USB-C |
| 6 | MODEM_READY | Chân STATUS của modem đang ở mức cao (v1.1) |
| 7 | SURVIVAL | Đang ở chế độ sinh tồn, chỉ thức khi có VBUS (v1.1) |

### CHG

| Bit | Tên | Mô tả |
|---|---|---|
| 0 | CHARGING | Đang sạc |
| 1 | CHARGE_DONE | Sạc xong |
| 2 | CHARGE_INHIBIT | Sạc bị cấm do nhiệt (phần cứng hoặc firmware) |
| 3 | CHARGE_TIMEOUT | Hết thời gian sạc an toàn (v1.1) |

### EVENT

| Bit | Tên | Mô tả |
|---|---|---|
| 0 | PIR | PIR vừa phát hiện chuyển động |
| 1 | SCHEDULE | Đến giờ theo lịch |
| 2 | VBUS_CHANGE | Cắm hoặc rút USB-C |
| 3 | LOW_BATT | Vừa xuống dưới ngưỡng cảnh báo |
| 4 | MODEM_STATUS | Chân STATUS của modem đổi mức |
| 5 | SHUTDOWN_REQ | MCU yêu cầu SoC tắt an toàn |
| 6 | WAKE_ALARM | Hết thời gian của kênh đánh thức khi ngủ (v1.1) |
| 7 | BUTTON | Nút nhấn (dự phòng, v1.1) |

### SYS_FLAGS

| Bit | Tên | Mô tả |
|---|---|---|
| 0 | WDT_RESET | Watchdog độc lập |
| 1 | POR_BOR | Cấp nguồn hoặc brown-out |
| 2 | PIN_RESET | Chân NRST |
| 3 | SOFTWARE | Reset mềm |
| 4 | CHG_INHIBIT | Sạc đang bị cấm do nhiệt |
| 5 | RTC_LOST | Mất giờ RTC |

## 3. Mã lệnh, lỗi, chế độ

### CMD

| Giá trị | Tên | Mô tả |
|---|---|---|
| 1 | SOC_WAKE | SoC đã thức, bắt đầu bắt tay |
| 2 | SOC_SHUTDOWN_DONE | SoC đã đóng file, sẵn sàng mất nguồn |
| 3 | MODEM_ON | Bật rail modem |
| 4 | MODEM_OFF | Tắt rail modem |
| 5 | MODEM_RESET | Xung RESET modem (v1.1) |
| 6 | CLEAR_FAULT | Xóa lỗi đang chốt (v1.1) |
| 7 | MODEM_PWRKEY | Xung PWRKEY modem (v1.1) |

### FAULT_CODE

| Giá trị | Tên | Mô tả |
|---|---|---|
| 0 | NONE | Không lỗi |
| 1 | BATT_UNDERVOLTAGE | Pin dưới ngưỡng tắt |
| 2 | BATT_OVERTEMP | Nhiệt độ pin cao |
| 3 | BATT_UNDERTEMP | Nhiệt độ pin thấp, cấm sạc |
| 4 | SOC_NO_HANDSHAKE | SoC không trả lời bắt tay tắt máy |
| 5 | SOC_NO_BOOT | SoC không báo SOC_READY trong thời gian cho phép |
| 6 | MODEM_NO_BOOT | Modem không lên trong thời gian cho phép |
| 7 | I2C_BUS | Lỗi bus I2C |
| 8 | SENSOR_STALE | Cảm biến nhiệt không đọc được |
| 9 | NVM | Lỗi bộ nhớ cấu hình |
| 10 | BAD_CMD | SoC ghi mã lệnh không hợp lệ |

### MODE

| Giá trị | Tên | Mô tả |
|---|---|---|
| 0 | ECO | Chỉ PIR và lịch, SoC và modem tắt |
| 1 | WATCH | Giữ modem để nhận lệnh trong vài giây |

### WAKE_CHAN

| Giá trị | Tên | Mô tả |
|---|---|---|
| 0 | OFF | Không dùng kênh đánh thức |
| 1 | MODEM_TCP_POLL | MCU hỏi cloud qua TCP stack của modem theo chu kỳ |
| 2 | SMS | Chỉ thức khi có SMS đánh thức |
| 3 | EDRX_MQTT | SoC thức, giữ MQTT (tốn pin, chỉ khi cần) |

## 4. Quy tắc truy cập

1. Thanh ghi nhiều byte là big-endian: byte cao ở địa chỉ thấp.
2. Đọc byte cao chốt (latch) toàn bộ nhóm; các byte sau trả giá trị đã chốt.
3. Ghi nhóm nhiều byte từ địa chỉ thấp tới cao; byte cuối cùng commit giá trị mới.
4. `EVENT` xóa khi đọc. Đọc trả các bit đã đặt rồi xóa chúng.
5. Ghi vào thanh ghi chỉ đọc, ghi ngoài dải, hoặc mã `CMD` lạ: NACK / đặt `BAD_CMD`.
6. Thanh ghi không định nghĩa trong bảng trên: NACK, không trả 0 im lặng.
