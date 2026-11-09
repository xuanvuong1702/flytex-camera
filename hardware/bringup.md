# Bring-up board prototype

Quy trình bật board lần đầu, theo thứ tự, có điểm dừng. Mỗi bước ghi kết quả vào [docs/08](../docs/08-kiem-chung.md) kèm ngày, rev board và dụng cụ.

Nguyên tắc: **cấp nguồn có giới hạn dòng** cho tới khi mọi rail đã đúng. Không bao giờ bật nguồn pack trực tiếp khi chưa đo chập.

## 0. Trước khi cấp nguồn

| Việc | Cách làm | Đạt khi |
|---|---|---|
| Kiểm thị giác | Soi gương, phóng đại 10× | Không cầu chì, không chân cong, có dấu chân 1 |
| Đo chập rail | Đồng hồ ở chế độ Ohm giữa từng rail và GND | Không có điện trở < 10 Ω (trừ đường có tải cố định) |
| Phân cực | Soi dấu + trên tụ hoá, diode, connector pin 1 | Khớp silkscreen |
| Jumper đo dòng | J_MEAS đóng, không có tải ngoài | Đã rõ |

Nếu có chập: dừng, tìm linh kiện, không "thử xem sao".

## 1. Cấp nguồn lần đầu (chưa gắn pack)

1. Nguồn bench 5,0 V, **giới hạn 100 mA**, cấp vào VBUS/USB-C.
2. Đo lần lượt: VBAT (qua sạc, nếu không có pack thì ~3,6 V), +3V3, +5V_BOOST.
3. Đo dòng không tải; ghi lại.
4. Tắt, tăng giới hạn 500 mA, bật lại, kiểm nhiệt IC sạc sau 1 phút.

**Đạt:** +3V3 trong 3,25–3,35 V; +5V_BOOST trong 4,9–5,1 V; không IC nào nóng bỏng tay; không reset lặp.

## 2. MCU và bus I2C

1. Nạp firmware MCU qua J_SWD (SWDIO, SWCLK, NRST, GND).
2. Nối master I2C (dev board hoặc bộ USB-I2C) vào SDA/SCL, địa chỉ `0x30`.
3. Đọc `PROTO_VER` (0x00) phải là `0x11`; đọc `STATUS` (0x02) không lỗi.
4. Đo `MCU_IRQ` đang mức cao (không sự kiện); kích PIR, thấy IRQ xuống thấp trong ≤ 200 ms.
5. Đọc `EVENT` để xóa, IRQ thả.

**Đạt:** M-12; không NACK; không treo bus.

## 3. SoC

1. Cắm thẻ/eMMC có image; nối UART console 115200 8N1.
2. Bật rail SoC bằng PIR/lịch hoặc ghi `CMD = SOC_WAKE`; MCU bật `+5V_SOC`.
3. Xem log khởi động, đăng nhập, chạy `python -m flytex.cli selftest`.
4. Kiểm mount `/data`, đọc `device_id`.

**Đạt:** log có, selftest 8/8, không kernel panic.

## 4. Camera và ghi hình

1. Kiểm FPC camera đúng chiều, khóa FPC.
2. Chạy `RkMpiSource` (hoặc lệnh capture của SDK) — xem ảnh qua relay/console.
3. Ghi 10 s vào thẻ; lấy file `.ts`, phát lại bằng máy tính (VLC/ffplay).
4. Rút điện đột ngột 10 lần khi đang ghi; kiểm chỉ mục và file không hỏng.

**Đạt:** M-18, M-20; file phát được; không mất quá một đoạn.

## 5. Modem và cloud

1. Lắp SIM, ăng-ten; kiểm `AT+CPIN?`, `AT+CSQ`, `AT+CREG?`.
2. Cấu hình APN, kiểm interface dữ liệu (`ip addr`).
3. Kết nối MQTT TLS bằng chứng chỉ thiết bị; xem `status` retained trên broker.
4. Gửi lệnh `status.get`, nhận `ack` đúng `id`.
5. Bật live, đo độ trễ và băng thông.

**Đạt:** M-30, M-31, M-33; ack đúng; không rớt kết nối khi tải.

## 6. Đo nguồn

1. Cắm PPK2 vào J_MEAS (hoặc shunt), đo từng trạng thái S0–S3.
2. Xuất CSV, nhập: `python -m tools.measure.cli ppk2 --csv trace.csv --id M-01 --out do.csv`.
3. Sinh báo cáo: `python -m tools.measure.cli report --csv do.csv`.

**Đạt:** M-01, M-02; các con số thay được ước tính trong [docs/02](../docs/02-thiet-ke-nguon.md).

## 7. Ngủ, đánh thức, nhiệt

1. Eco: PIR và lịch đánh thức; đo dòng ngủ 24 h (M-02).
2. Watch: gửi SMS có token; đo độ trễ và dòng (M-35).
3. Bắt tay tắt máy: theo dõi `SHUTDOWN_REQ` → `SOC_SHUTDOWN_DONE` → rail cắt (M-13).
4. Tủ sấy 60 °C, ghi 1 h (M-22); đo mặt vỏ khi nắng (M-40).

**Đạt:** không reset, không hỏng thẻ, nhiệt trong giới hạn.

## 8. Khi không đạt

Dừng bước, ghi vào [docs/10](../docs/10-rui-ro.md) hoặc nhật ký quyết định, nêu thay đổi thiết kế. Không hạ tiêu chí và không bỏ qua bước.
