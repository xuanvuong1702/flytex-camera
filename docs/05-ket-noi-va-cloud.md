# 05 — Kết nối và cloud

- Trạng thái: v1.1, cập nhật 2026-11-09 theo [13](13-tinh-kha-thi.md)
- Ngày: 2026-11-09
- **Giao thức chi tiết đã chuyển sang [15](15-giao-thuc-va-cloud.md).** Tài liệu này giữ phần quyết định và lý do; số liệu nguồn ở `spec/mqtt.toml` và `spec/b2b.toml`.

## 1. Modem

Ứng viên: Quectel **EC200U-EU** `[KẾ THỪA]` trên breakout cắm vào header của CMP. Dự phòng cùng tầm: SIMCom A7670E.

### 1.1 Đường dữ liệu: USB cho dữ liệu, UART cho lệnh AT `[ĐỀ XUẤT]`

Dự án CAM4G chạy PPP qua UART ở 921600 baud. Một byte UART 8N1 chiếm 10 bit, nên 921600 baud cho tối đa khoảng 92 KB/s, tức khoảng **0,74 Mbps**, thấp hơn mức 1–2 Mbps mà chính CAM4G đặt cho live 720p. Datasheet Quectel EC200U (V1.4) liệt kê USB 2.0 High Speed và driver RNDIS, ECM cho Linux, nên USB là đường dữ liệu tự nhiên; UART giữ cho lệnh AT.

**Chốt:** USB cho dữ liệu, UART cho AT. Nhưng Core1106 chỉ có **một** cổng USB `[ĐÃ XÁC MINH]`, nên phải có mux hoặc đường nạp dự phòng ([03](03-giao-dien.md) §4.1). O-01 đã đóng; D-13 giữ nguyên (USB-C chỉ cấp nguồn).

Chưa xác minh:

- tốc độ baud tối đa của UART trên EC200U (datasheet đã xem không nêu);
- kernel của SDK Core1106 có driver ECM/RNDIS hay không;
- mux USB cụ thể và cách điều khiển (O-13).

### 1.2 Yêu cầu với breakout

Chọn loại thỏa **tất cả**:

1. Nhận 5 V, tự hạ xuống khoảng 3,8 V cho module, đủ **≥1,8 A đỉnh** để chịu burst. (EC200U cần VBAT 3,3–4,3 V `[KẾ THỪA]`.) Con số 1,8 A là cận trên thiết kế, xem [13](13-tinh-kha-thi.md) F-03.
2. Đổi mức 1,8 V ↔ 3,3 V cho các tín hiệu UART và điều khiển.
3. Đưa USB D+/D− ra header.
4. Tụ bulk ≥ 470 µF trên đầu vào 5 V, đặt sát module.
5. Khe SIM nano và u.FL.
6. **Đưa `RI` ra header**, để MCU nhận đánh thức SMS.

Nếu không có breakout đủ các mục trên, ghi nhận vào O-04 và thêm mạch tương ứng.

### 1.3 Băng tần và APN

Theo tài liệu CAM4G, EC200U-EU hỗ trợ LTE-FDD B1/B3/B5/B7/B8/B20/B28; cần đối chiếu với băng tần của từng nhà mạng Việt Nam trước khi chốt `[CHƯA XÁC MINH]`. APN lấy từ nhà mạng khi cấu hình SIM, không ghi cứng.

## 2. Nhận lệnh khi ngủ

Bản nháp v0.1 đặt "eDRX + MQTT" cho chế độ Watch, nhưng ở Watch **SoC tắt**, nên không có máy nào chạy MQTT. Đó là lỗ hổng kiến trúc ([13](13-tinh-kha-thi.md) F-02). Thiết kế chốt:

```
Cloud ──SMS "W <token>"──► Modem (eDRX) ──RI──► MCU ──► bật +5V_SOC
                                                        └─► SoC đọc SMS, xác thực, kết nối MQTT
```

| Phương án | Độ trễ lệnh | Dòng ước tính | Ghi chú |
|---|---|---|---|
| **SMS + RI (chốt cho Watch)** | 5–30 s | 3–5 mA | Cần chân `MODEM_RI`; tốn một SMS mỗi lần đánh thức |
| eDRX + MQTT với SoC bật | 1–2 s | 130–300 mW | Chỉ dùng khi cần, pin ~7 ngày |
| Hỏi server định kỳ | 1–5 phút | 0,2–1 mA | Cần UART phụ modem→MCU (O-12) |
| PSM + thức theo lịch | 30–60 phút | ~0,05 mA | Eco; không nhận downlink kịp |

Các con số là `[KẾ THỪA]` `[ƯỚC TÍNH]`; thay bằng M-03, M-32, M-35. **Rủi ro:** eDRX phải được mạng cấp; nếu không, SMS đến trễ hàng giờ khi máy ở PSM (R-07).

## 3. Xem trực tiếp

Mục tiêu độ trễ ≤ 1,5 s `[KẾ THỪA]` `[CHƯA XÁC MINH]`. Ngân sách trễ ở [15](15-giao-thuc-va-cloud.md) §6.2 cho thấy chỉ WebRTC đạt; HLS không đạt.

`[ĐỀ XUẤT]` Dùng **MediaMTX** làm relay: thiết bị đẩy RTSP/SRT, ứng dụng phát bằng **WHEP**. Cách này tránh tự viết signaling WebRTC và xử lý NAT phía thiết bị (thiết bị chủ động kết nối ra, qua được CGNAT). Chưa đo; đo ở G0 bằng đường 4G thật (M-31).

Băng thông tải lên cho 720p khoảng 1–2 Mbps `[ƯỚC TÍNH]`. Cat-1 không phải lúc nào cũng cho được mức này ở vùng sóng yếu; phải có bitrate thích ứng ([15](15-giao-thuc-va-cloud.md) §6.3).

## 4. Cloud

| Thành phần | Chọn | Ghi chú |
|---|---|---|
| Điều khiển và sự kiện | MQTT broker có TLS | QoS 1, chủ đề theo thiết bị ([15](15-giao-thuc-va-cloud.md) §5) |
| Video trực tiếp | MediaMTX (WebRTC/WHEP) | Xác thực theo thiết bị, token ngắn hạn |
| Clip | Kho đối tượng | Tải qua HTTPS, không qua MQTT |
| Định danh | Chứng chỉ riêng từng thiết bị | Cấp lúc sản xuất, không chung cho cả lô |

Chủ đề MQTT, phong bì, lệnh và ack: xem [15](15-giao-thuc-va-cloud.md) §5. Không chép lại ở đây.

### Quyền riêng tư

Video là dữ liệu nhạy cảm: mã hóa trên đường truyền, quy định thời gian lưu, và quyền truy cập theo tài khoản. SMS đánh thức chỉ chứa token, không chứa nội dung.

## 5. Bảo mật tối thiểu cho bản tiền thương mại

- TLS mọi kết nối.
- Chứng chỉ riêng từng thiết bị; khả năng thu hồi.
- Không có mật khẩu mặc định chung; console UART chỉ có khi mở vỏ.
- Token SMS dùng một lần, có hạn.
- Cập nhật có chữ ký (khi OTA làm được).
