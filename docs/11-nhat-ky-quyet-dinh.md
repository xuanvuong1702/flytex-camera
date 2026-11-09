# 11 — Nhật ký quyết định

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

Ba nhóm: đã chốt, đề xuất (chờ xác nhận), và câu hỏi mở. Khi một mục đổi trạng thái, ghi ngày và lý do thay vì xóa.

## 1. Đã chốt

| ID | Quyết định | Ngày | Ghi chú |
|---|---|---|---|
| D-01 | Làm lại từ đầu; tài liệu nằm ở repo này, không kế thừa file thiết kế của CAM4G | 2026-11-09 | Kế thừa bài học ([12](12-bai-hoc-tu-cam4g.md)) |
| D-02 | Pin là pack 1S LFP có sẵn BMS, không tự ghép cell | 2026-11-09 | Kéo theo mục 7 của [02](02-thiet-ke-nguon.md) |
| D-03 | Sạc bằng USB-C 5 V | 2026-11-09 | Giữ pack 1S và boost; không dùng pack điện áp cao với buck |

## 2. Đề xuất

| ID | Đề xuất | Lý do | Điều kiện xác nhận |
|---|---|---|---|
| D-04 | Tách PWR, CMP, MDM | Mỗi board một luật layout, mỗi lần đặt chỉ sửa một board | Chủ dự án đồng ý |
| D-05 | Giữ MCU giám sát | Luôn bật, quản lý nguồn và PIR | Đo dòng ở G2 |
| D-06 | Không dùng INA226; dùng header đo dòng ngoài | Chip không đo được dòng ngủ; bớt linh kiện | |
| D-07 | Modem: USB cho dữ liệu, UART cho AT | UART 921600 baud không đủ cho video | Xác minh ở G0 (O-01) |
| D-08 | Camera có IR-CUT và LED IR tích hợp | Bớt mạch điều khiển IR | Chọn module (O-02) |
| D-09 | Core1106 dạng module OEM, chưa chip-down | Giảm rủi ro và công sức | |
| D-10 | Giai đoạn 0 đo trên dev board | Mọi con số công suất đang là ước tính | |
| D-11 | Board thử footprint trước mỗi lần spin | Footprint là nhóm lỗi nhiều nhất ở CAM4G | |
| D-12 | Relay mã nguồn mở cho xem trực tiếp | Tránh tự viết signaling | Thử độ trễ ở G0 |
| D-13 | USB-C chỉ cấp nguồn, không nối D+/D− | Cổng USB của SoC dành cho modem | Xác minh (O-01) |
| D-14 | Board PWR thiết kế cho pack tới 15 Ah; prototype 10 Ah | 10 Ah gần như không dư cho kịch bản đêm | Đo ở G0 |
| D-15 | NTC cắt sạc đặt trên pack | Đo đúng nhiệt độ cell | Pack có dây NTC (O-03) |
| D-16 | Prototype dùng bộ sạc tuyến tính, sạc khi nghỉ; production dùng bộ sạc xung có power-path | Đơn giản trước, chuẩn sau | O-05 |

## 3. Câu hỏi mở

| ID | Câu hỏi | Cần để | Đóng ở |
|---|---|---|---|
| O-01 | Core1106 có mấy cổng USB? Có host cho modem đồng thời với nạp firmware không? | D-07, D-13 | G0 |
| O-02 | Module camera cụ thể và pinout FPC 20 chân | Vẽ CMP | G0 |
| O-03 | Pack LFP và BMS cụ thể: dòng xả, ngưỡng, NTC, khôi phục, giấy tờ | Mục 7 của [02](02-thiet-ke-nguon.md) | G0 |
| O-04 | Breakout EC200U-EU nào đủ yêu cầu (USB ra, hạ áp, đổi mức)? | Header J_MODEM | G0 |
| O-05 | Chip sạc production và power-path | Giai đoạn 5 | G2 |
| O-06 | Giải pháp cổng USB-C chống nước | Vỏ | G4 |
| O-07 | Vị trí và loại ăng-ten 4G với vỏ nhôm | Vỏ | G0 |
| O-08 | OTA có khả thi trên SDK Core1106 không? | FR-07 | G0 |
| O-09 | eDRX/PSM có dùng được trên các nhà mạng Việt Nam không? | Chế độ Watch | G0 |
| O-10 | Lộ trình chứng nhận và quy định tại Việt Nam | Giai đoạn 5 | G5 |
| O-11 | Số cổng GPIO, UART mà Core1106 mở ra có đủ cho J_B2B và header | Vẽ CMP | G0 |
