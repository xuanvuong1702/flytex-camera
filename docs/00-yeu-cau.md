# 00 — Yêu cầu

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

Các yêu cầu mang nhãn `[KẾ THỪA]` lấy từ dự án CAM4G và phải được chủ dự án xác nhận lại trước khi dùng làm tiêu chí nghiệm thu.

## 1. Mục tiêu sản phẩm

Camera ngoài trời chạy pin, kết nối 4G, dùng được ở nơi không có điện lưới và không có Wi-Fi. Phiên bản tiền thương mại phải:

- chạy được ngoài hiện trường với một nhóm nhỏ người dùng thử;
- dựng được prototype nhanh và rẻ, ít vòng đặt board;
- giữ các giao diện ổn định để chuyển sang sản xuất mà không thiết kế lại.

## 2. Yêu cầu chức năng

| ID | Yêu cầu | Nhãn | Cách kiểm chứng |
|---|---|---|---|
| FR-01 | Ghi hình 720p lên microSD khi có chuyển động | `[KẾ THỪA]` | M-20 |
| FR-02 | Phát hiện chuyển động bằng PIR và đánh thức hệ thống từ ngủ sâu | `[KẾ THỪA]` | M-12 |
| FR-03 | Xem trực tiếp qua 4G, độ trễ mục tiêu ≤ 1,5 s | `[KẾ THỪA]` `[CHƯA XÁC MINH]` | M-31 |
| FR-04 | Nhận lệnh từ xa khi ngủ, có hai chế độ: **Watch** (nhận lệnh trong vài giây) và **Eco** (chỉ PIR và lịch) | `[KẾ THỪA]` | M-03, M-32 |
| FR-05 | Ban đêm có hồng ngoại, tầm ≤ 3 m, IR-CUT tự động | `[KẾ THỪA]` | M-21 |
| FR-06 | Gửi sự kiện (chuyển động, pin, nhiệt độ) lên cloud | `[ĐỀ XUẤT]` | M-30 |
| FR-07 | Cập nhật firmware từ xa (OTA) | `[ĐỀ XUẤT]` `[CHƯA XÁC MINH]` | xem O-08 |
| FR-08 | Mỗi thiết bị có định danh và thông tin xác thực riêng | `[ĐỀ XUẤT]` | M-33 |
| FR-09 | Sạc pin qua USB-C 5 V | `[ĐÃ CHỐT]` | M-04 |
| FR-10 | Cấm sạc khi nhiệt độ pin cao hơn khoảng 40 °C, thực hiện bằng phần cứng, không phụ thuộc firmware | `[KẾ THỪA]` | M-05 |

## 3. Yêu cầu phi chức năng

| ID | Yêu cầu | Nhãn |
|---|---|---|
| NFR-01 | Nguồn: pack LFP 1S có BMS. Dung lượng prototype 10 Ah; board nguồn thiết kế cho tới 15 Ah (xem [02](02-thiet-ke-nguon.md) §3) | `[ĐÃ CHỐT]` (pack có BMS), `[ĐỀ XUẤT]` (dung lượng) |
| NFR-02 | Không khí 40–45 °C, bề mặt vỏ tới khoảng 70 °C. Core1106 chỉ được định mức −20…+60 °C nên phải tản nhiệt qua vỏ | `[KẾ THỪA]` |
| NFR-03 | Ghi liên tục 7 giờ. Ban ngày phải đạt; ban đêm bật IR và live chỉ đạt nếu pin đủ (xem [02](02-thiet-ke-nguon.md) §3) | `[KẾ THỪA]` |
| NFR-04 | Dòng trung bình ở chế độ Eco ngủ sâu < 1 mA | `[KẾ THỪA]` `[CẦN ĐO]` |
| NFR-05 | Cấp bảo vệ mục tiêu IP65 | `[ĐỀ XUẤT]` |
| NFR-06 | Mọi linh kiện SMD lắp bằng PCBA; hàn tay chỉ dành cho connector xuyên lỗ | `[ĐỀ XUẤT]` |
| NFR-07 | Mọi board có test point cho từng rail, đầu SWD và UART console | `[ĐỀ XUẤT]` |
| NFR-08 | Mọi rail 3,3 V logic giữa các board; việc đổi mức 1,8 V của modem do breakout lo | `[ĐỀ XUẤT]` |

## 4. Ngoài phạm vi (bản tiền thương mại)

- SoC chip-down (tự layout DDR, nguồn SoC). Dùng module OEM.
- Khuôn đúc vỏ. Dùng vỏ có sẵn hoặc gia công CNC.
- Hoàn tất chứng nhận. Chỉ chuẩn bị (xem [09](09-san-xuat.md) §6).
- Ứng dụng di động hoàn chỉnh, nhận diện người bằng AI.
- Sạc bằng năng lượng mặt trời, PoE, Wi-Fi.

## 5. Giả định cần xác nhận

| ID | Giả định | Nhãn |
|---|---|---|
| A-01 | SoC là module Core1106G3 N256 | `[KẾ THỪA]` |
| A-02 | Modem là Quectel EC200U-EU trên breakout | `[KẾ THỪA]` |
| A-03 | Camera là module cảm biến SC3336 dạng FPC 20 chân, nên chọn loại có IR-CUT và LED IR tích hợp | `[KẾ THỪA]` `[ĐỀ XUẤT]` |
| A-04 | Dùng SIM dữ liệu của các nhà mạng Việt Nam | `[KẾ THỪA]` |
| A-05 | PIR dùng loại AM312 hoặc tương đương | `[KẾ THỪA]` |

## 6. Câu hỏi mở

Danh sách đầy đủ ở [11-nhat-ky-quyet-dinh.md](11-nhat-ky-quyet-dinh.md) §3. Những câu quyết định kiến trúc sớm nhất:

- Core1106 có mấy cổng USB? (O-01)
- Module camera cụ thể là loại nào, pinout ra sao? (O-02)
- Pack LFP và BMS cụ thể là loại nào? (O-03)
