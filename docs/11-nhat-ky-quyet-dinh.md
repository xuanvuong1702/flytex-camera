# 11 — Nhật ký quyết định

- Trạng thái: v1.3, chốt thêm 4 quyết định ngày 2026-11-09
- Ngày: 2026-11-09

Ba nhóm: đã chốt, đề xuất (chờ xác nhận), và câu hỏi mở. Khi một mục đổi trạng thái, ghi ngày và lý do thay vì xóa.

## 1. Đã chốt

| ID | Quyết định | Ngày | Ghi chú |
|---|---|---|---|
| D-01 | Làm lại từ đầu; tài liệu nằm ở repo này, không kế thừa file thiết kế của CAM4G | 2026-11-09 | Kế thừa bài học ([12](12-bai-hoc-tu-cam4g.md)) |
| D-02 | Pin là pack 1S LFP có sẵn BMS, không tự ghép cell | 2026-11-09 | Kéo theo mục 7 của [02](02-thiet-ke-nguon.md) |
| D-03 | Sạc bằng USB-C 5 V | 2026-11-09 | Giữ pack 1S và boost; không dùng pack điện áp cao với buck |
| D-16 | Dùng **bộ sạc có power-path ngay từ Rev A**, không dùng sạc tuyến tính | 2026-11-09 | Chủ dự án chốt. Lý do: F-04 — 0,5 A cần 20–30 giờ và tải không bao giờ đầy. **Sửa 2026-11-09:** yêu cầu "xung" hạ xuống "float LFP bằng phần cứng + power-path"; IC cụ thể chưa chọn (O-05), BQ25798 bị loại |
| D-18 | Pack LFP 1S **15 Ah** (48 Wh danh định) | 2026-11-09 | Chủ dự án chốt. 10 Ah không còn dư cho kịch bản đêm (F-05). Kéo theo: BMS sạc ≥1,5 A, tự tiêu ≤100 µA |
| D-19 | Module **eMMC 8 GB** (Core1106D1408 hoặc D1808), không dùng bản 256 MB SPI NAND | 2026-11-09 | Chủ dự án chốt. NAND không đủ OTA A/B + runtime Python (F-08) |
| D-21 | Đổi một chân dự phòng trên J_B2B lấy `MODEM_RI` (chân 21) | 2026-11-09 | Chủ dự án chốt. RI là đường đánh thức SMS; ban đầu còn 2 chân dự phòng, sau D-22 còn 1 |
| D-22 | Dùng chân 20 (trước là `SPARE_SOC1`) làm `USB_SEL` do MCU điều khiển | 2026-11-09 | Chốt sau rà soát: mux USB cần chân điều khiển mà J_B2B chưa có; giữ chân 20 là spare sẽ không bao giờ chọn được mux. Số chân dự phòng còn 1 (`SPARE_SOC2`). Mux cụ thể vẫn ở O-13 |
| D-24 | J_B2B: PWR dùng header đực `TSM-113-01-L-DV`, CMP dùng socket cái `SSM-113-L-DV`; cắt chân 26 làm khóa | 2026-11-09 | Trước đây cả hai board đều dùng header đực, không ghép được và không khóa. Cắt chân 26 tạo khóa cơ khí; ghi rõ trong bản vẽ lắp ráp |
| D-25 | Dòng sạc BQ25070 đặt bằng **11 xung CTRL = 935 mA**; MCU phát xung lúc boot qua chân `CHG_CTRL` | 2026-11-09 | CTRL là giao diện xung một dây, không có điện trở. Không gửi xung chỉ 285 mA. Giữ CTRL cao >2 ms để ngắt sạc |
| D-23 | Chọn **BQ25070** làm IC sạc: LFP 1S, float 3,5 V cố định, power-path, NTC, standalone 1 A | 2026-11-09 | Thay BQ25798 (mặc định 4,2 V + watchdog). Đánh đổi: sạc tuyến tính ~1,5 W, 15 Ah mất ~12 h; chấp nhận cho prototype để đổi lấy an toàn. Còn phải tính CTRL và mạng NTC theo datasheet |

## 2. Đề xuất

| ID | Đề xuất | Lý do | Điều kiện xác nhận |
|---|---|---|---|
| D-04 | Tách PWR, CMP, MDM | Mỗi board một luật layout, mỗi lần đặt chỉ sửa một board | Chủ dự án đồng ý |
| D-05 | Giữ MCU giám sát | Luôn bật, quản lý nguồn và PIR | Đo dòng ở G2 |
| D-06 | Không dùng INA226; dùng header đo dòng ngoài | Chip không đo được dòng ngủ; bớt linh kiện | |
| D-07 | Modem: USB cho dữ liệu, UART cho AT | UART 921600 baud không đủ cho video | G0 |
| D-08 | Camera có IR-CUT và LED IR tích hợp | Bớt mạch điều khiển IR | Chọn module (O-02) |
| D-09 | Core1106 dạng module OEM, chưa chip-down | Giảm rủi ro và công sức | |
| D-10 | Giai đoạn 0 đo trên dev board | Mọi con số công suất đang là ước tính | |
| D-11 | Board thử footprint trước mỗi lần spin | Footprint là nhóm lỗi nhiều nhất ở CAM4G | |
| D-12 | Relay mã nguồn mở cho xem trực tiếp | Tránh tự viết signaling | Thử độ trễ ở G0 |
| D-13 | USB-C chỉ cấp nguồn, không nối D+/D− | Cổng USB của SoC dành cho modem | **Đã xác nhận bằng tài liệu kỹ thuật**: Core1106 có 1 cổng USB; đây vẫn là đề xuất chờ chủ dự án chốt |
| D-14 | Board PWR thiết kế cho pack tới 15 Ah | Nay D-18 chốt đúng 15 Ah | Đã đáp ứng bởi D-18 |
| D-15 | NTC cắt sạc đặt trên pack | Đo đúng nhiệt độ cell | Pack có dây NTC (O-03) |
| D-17 | Kênh đánh thức khi ngủ: **SMS + `MODEM_RI`**; `EDRX_MQTT` chỉ dùng khi cần độ trễ thấp; `MODEM_TCP_POLL` chờ O-12 | Ở chế độ Watch SoC tắt, không ai giữ MQTT; MCU không chạy TLS ([13](13-tinh-kha-thi.md) F-02) | Thử ba mạng (M-35) |
| D-20 | Đường nạp dịch vụ: pad USB trên board + mux USB 2.0 điều khiển bằng GPIO (phương án A) | Một cổng USB vừa cho modem vừa cho nạp (F-01) | Chốt ở G0 sau khi thử (M-34) |
| D-22 | Xem trực tiếp dùng **WebRTC/WHEP** qua MediaMTX, không dùng HLS | HLS 2–6 s, không đạt 1,5 s (F-06) | Đo M-31, M-39 |
| D-23 | Regmap v1.1: mọi trường nhiều byte big-endian; `spec/*.toml` là nguồn sự thật, mã và bảng sinh tự động | Bản nháp mâu thuẫn little/big-endian; chép tay gây trôi số liệu | Chủ dự án xác nhận |
| D-24 | Ứng dụng Linux viết bằng **Python 3 thuần thư viện chuẩn**, paho-mqtt là tùy chọn | Dựng nhanh, test được trên máy tính; camera và mã hóa vẫn do SDK C lo | Đo RAM/flash trên thiết bị (R-27) |
| D-25 | CI chạy `spec/generate.py --check`, test firmware/app/tools, mô phỏng end-to-end | Thực thi nguyên tắc "mỗi con số một nguồn" bằng máy, không bằng lời hứa | |
| D-26 | Hợp đồng MQTT theo `spec/mqtt.toml`: phong bì chung, QoS 1, `status` retained, `ack` theo `id`, lệnh dạng phẳng (`type` = tên lệnh) | Một nguồn cho cả thiết bị và cloud | Cloud team xác nhận |

## 3. Câu hỏi mở

| ID | Câu hỏi | Cần để | Trạng thái |
|---|---|---|---|
| O-01 | Core1106 có mấy cổng USB? Có host cho modem đồng thời với nạp firmware không? | D-07, D-13 | **Đã đóng 2026-11-09**: đúng 1 cổng USB 2.0 Host/Device, theo [tài liệu Luckfox Core1106D](https://wiki.luckfox.com/Core1106D/Introduction/). Hệ quả: D-20 |
| O-02 | Module camera cụ thể và pinout FPC 20 chân | Vẽ CMP | Mở — chặn layout CMP |
| O-03 | Pack LFP và BMS cụ thể: dòng xả, dòng sạc ≥1,5 A, tự tiêu ≤100 µA, NTC, khôi phục, giấy tờ | Mục 7 của [02](02-thiet-ke-nguon.md) | Mở — chặn mua pack |
| O-04 | Breakout EC200U-EU nào đủ yêu cầu (USB ra, hạ áp, đổi mức, **RI ra header**)? | Header J_MODEM | Mở |
| O-05 | IC sạc LFP 1S float bằng phần cứng, power-path, NTC. **Đã chọn BQ25070** (D-23) | Layout PWR Rev A | Đóng phần chọn IC; còn mở phần tính CTRL/NTC và kiểm tồn kho |
| O-06 | Giải pháp cổng USB-C chống nước | Vỏ | Mở |
| O-07 | Vị trí và loại ăng-ten 4G với vỏ nhôm | Vỏ | Mở |
| O-08 | OTA có khả thi trên SDK Core1106 không? A/B có vừa eMMC không? | FR-07 | Mở |
| O-09 | eDRX/PSM có dùng được trên các nhà mạng Việt Nam không? | Chế độ Watch | Mở |
| O-10 | Lộ trình chứng nhận và quy chuẩn áp dụng tại Việt Nam | Giai đoạn 5 | Mở — hỏi sớm, trước khi làm vỏ |
| O-11 | Số cổng GPIO, UART mà Core1106 mở ra có đủ cho J_B2B và header? | Vẽ CMP | Mở — đã biết module có 6 UART, 5 I2C, 12 PWM nhưng chưa biết chân nào ra stamp hole |
| O-12 | EC200U có bộ lệnh MQTT hoặc UART phụ để MCU tự hỏi cloud không? | Kênh `MODEM_TCP_POLL` | Mở — nếu đóng, Watch có thêm phương án dự phòng |
| O-13 | Mux USB cụ thể (ví dụ TS3USB221A) và ai điều khiển `USB_SEL`? | J_B2B phiên bản sau, layout CMP | Mở |
| O-14 | Có cần gauge pin để báo phần trăm không, hay chỉ báo mV? | Ứng dụng, UI | Mở — LFP có đường cong phẳng, đừng suy phần trăm từ điện áp |
| O-15 | Buck 3,3 V: dùng bản cố định 3,3 V hay bản chỉnh được (cần thêm cặp điện trở hồi tiếp)? Vref và gói DLC là gì? | BOM, schematic PWR | Mở — blocker trong [18](18-tai-lieu-linh-kien.md) §2.1 |
| O-16 | +3V3 hiện là buck, nên chỉ 3,0–3,3 V khi chạy pin. Có cần đổi sang buck-boost 3,3 V để nuôi DS18B20/rail logic không? | BOM, đo G0 | Mở — quyết định sau M-02/M-41; nếu DS18B20 hoặc bus không ổn định ở 3,0 V thì đổi |
