# 05 — Kết nối và cloud

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Modem

Ứng viên: Quectel **EC200U-EU** `[KẾ THỪA]` trên breakout cắm vào header của CMP. Dự phòng cùng tầm: SIMCom A7670E.

### 1.1 Đường dữ liệu: USB cho dữ liệu, UART cho lệnh AT `[ĐỀ XUẤT]`

Dự án CAM4G chạy PPP qua UART ở 921600 baud. Một byte UART 8N1 chiếm 10 bit, nên 921600 baud cho tối đa khoảng 92 KB/s, tức khoảng **0,74 Mbps**, thấp hơn mức 1–2 Mbps mà chính CAM4G đặt cho live 720p. Datasheet Quectel EC200U (V1.4) liệt kê USB 2.0 High Speed và driver RNDIS, ECM cho Linux, nên USB là đường dữ liệu tự nhiên; UART giữ cho lệnh AT.

Chưa xác minh:

- tốc độ baud tối đa của UART trên EC200U (datasheet đã xem không nêu);
- kernel của SDK Core1106 có driver ECM/RNDIS hay không;
- Core1106 có mấy cổng USB và có dùng được làm host đồng thời với việc nạp firmware hay không (O-01).

Nếu Core1106 chỉ có một cổng USB, cổng đó dành cho modem; USB-C chỉ cấp nguồn ([02](02-thiet-ke-nguon.md) §6.1) và nạp SoC qua SD hoặc pad riêng.

### 1.2 Yêu cầu với breakout

Chọn loại thỏa **tất cả**:

1. Nhận 5 V, tự hạ xuống khoảng 3,8 V cho module, đủ ≥ 0,6 A đỉnh. (EC200U cần VBAT 3,3–4,3 V `[KẾ THỪA]`.)
2. Đổi mức 1,8 V ↔ 3,3 V cho các tín hiệu UART và điều khiển.
3. Đưa USB D+/D− ra header.
4. Tụ bulk ≥ 470 µF trên đầu vào 5 V.
5. Khe SIM nano và u.FL.

Nếu không có breakout đủ các mục trên, ghi nhận vào O-04 và thêm mạch tương ứng.

### 1.3 Băng tần và APN

Theo tài liệu CAM4G, EC200U-EU hỗ trợ LTE-FDD B1/B3/B5/B7/B8/B20/B28; cần đối chiếu với băng tần của từng nhà mạng Việt Nam trước khi chốt `[CHƯA XÁC MINH]`. APN lấy từ nhà mạng khi cấu hình SIM, không ghi cứng.

## 2. Nhận lệnh khi ngủ

| Phương án | Độ trễ lệnh | Dòng ước tính | Ghi chú |
|---|---|---|---|
| A. Modem giữ DRX thường | < 2–5 s | 2–5 mA | Nhanh nhất, tốn pin nhất |
| B. eDRX + MQTT | 5–15 s | 1–3 mA | Mặc định của chế độ Watch |
| C. Hỏi server định kỳ | 1–5 phút | 0,2–1 mA | Đơn giản |
| D. PSM + thức theo lịch | 30–60 phút | khoảng 0,05 mA | Gần như offline, hợp chế độ Eco |

Các con số lấy từ CAM4G `[KẾ THỪA]` `[ƯỚC TÍNH]`. **Rủi ro lớn:** hiệu lực của eDRX và PSM phụ thuộc nhà mạng cho phép; cần thử trên cả ba nhà mạng (R-07). Nếu mạng không hỗ trợ, chế độ Watch chỉ còn phương án A hoặc C, và mục tiêu tuổi thọ phải tính lại.

## 3. Xem trực tiếp

Mục tiêu độ trễ ≤ 1,5 s `[KẾ THỪA]` `[CHƯA XÁC MINH]`.

`[ĐỀ XUẤT]` Dùng một **relay mã nguồn mở** (ví dụ MediaMTX): camera đẩy luồng lên relay, relay phát lại cho ứng dụng. Cách này tránh tự viết signaling WebRTC và xử lý NAT phía thiết bị. Chưa thử độ trễ; đo ở giai đoạn 0 trên dev board bằng đường 4G thật.

Băng thông tải lên cần cho 720p khoảng 1–2 Mbps `[ƯỚC TÍNH]`. Cat-1 không phải lúc nào cũng cho được mức này ở vùng sóng yếu; đo thực (M-30).

## 4. Cloud

| Thành phần | Chọn | Ghi chú |
|---|---|---|
| Điều khiển và sự kiện | MQTT broker có TLS | QoS 1, chủ đề theo thiết bị |
| Video trực tiếp | Relay (mục 3) | Xác thực theo thiết bị |
| Clip | Kho đối tượng | Tải khi có mạng tốt hoặc theo yêu cầu |
| Định danh | Chứng chỉ hoặc token riêng cho từng thiết bị | Cấp lúc sản xuất, không chung cho cả lô |

### Chủ đề MQTT (dự thảo)

| Chủ đề | Hướng | Nội dung |
|---|---|---|
| `dev/{id}/event` | thiết bị → cloud | Chuyển động, pin, nhiệt, lỗi |
| `dev/{id}/status` | thiết bị → cloud | Trạng thái, tín hiệu, phiên bản |
| `dev/{id}/cmd` | cloud → thiết bị | Live, đổi chế độ, đặt lịch |
| `dev/{id}/ack` | thiết bị → cloud | Xác nhận lệnh theo ID |

### Quyền riêng tư

Video là dữ liệu nhạy cảm: mã hóa trên đường truyền, quy định thời gian lưu, và quyền truy cập theo tài khoản.

## 5. Bảo mật tối thiểu cho bản tiền thương mại

- TLS mọi kết nối.
- Chứng chỉ riêng từng thiết bị; khả năng thu hồi.
- Không có mật khẩu mặc định chung; console UART chỉ có khi mở vỏ.
- Cập nhật có chữ ký (khi OTA làm được).
