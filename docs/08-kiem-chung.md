# 08 — Kiểm chứng

- Trạng thái: Dự thảo v0.1. **Chưa có phép đo nào được thực hiện.**
- Ngày: 2026-11-09

Quy tắc: mỗi kết quả ghi ngày, phiên bản board, điều kiện đo, dụng cụ và người đo. Chưa đo thì trạng thái là "Chưa làm", không điền con số.

## 1. Giai đoạn 0 — Dev board

| ID | Phép đo | Tiêu chí | Trạng thái |
|---|---|---|---|
| M-01 | Công suất từng trạng thái S0–S3, có và không có IR | Ghi bảng; thay các ước tính ở [02](02-thiet-ke-nguon.md) §3 | Chưa làm |
| M-02 | Dòng ngủ Eco trung bình 24 giờ | < 1 mA (NFR-04) | Chưa làm |
| M-03 | Dòng và độ trễ lệnh của Watch | Ghi lại; so với 5–15 s | Chưa làm |
| M-30 | Băng thông tải lên 4G, ba nhà mạng | ≥ 2 Mbps `[KẾ THỪA]` | Chưa làm |
| M-31 | Độ trễ xem trực tiếp qua relay | ≤ 1,5 s `[KẾ THỪA]` | Chưa làm |
| M-32 | eDRX/PSM có được mạng chấp nhận | Ghi theo từng nhà mạng | Chưa làm |

## 2. Board PWR

| ID | Phép đo | Tiêu chí | Trạng thái |
|---|---|---|---|
| M-04 | Sạc LFP: điện áp cuối, dòng sạc, kết thúc | Điện áp cuối đúng ngưỡng cell, dưới ngưỡng quá áp của BMS | Chưa làm |
| M-05 | Điểm cắt sạc theo nhiệt (tủ sấy, nhiệt kế đối chứng) | Ghi điểm cắt thực; dự kiến 35–40 °C | Chưa làm |
| M-06 | Rail 5 V dưới tải 3 A | 4,9–5,1 V | Chưa làm |
| M-07 | Rail 3,3 V | 3,25–3,35 V | Chưa làm |
| M-08 | Gợn và quá độ khi modem phát và IR bật | Ghi bằng máy hiện sóng; không gây reset | Chưa làm |
| M-09 | Dòng nghỉ không tải của PWR (MCU ngủ) | Ghi lại | Chưa làm |
| M-10 | Dòng nghỉ của boost và breakout modem ở Watch | Ghi lại (R-04) | Chưa làm |
| M-11 | Hành vi sạc khi tải chạy | Ghi nhận giới hạn "chỉ sạc khi nghỉ" | Chưa làm |
| M-12 | PIR đánh thức: từ PIR tới `MCU_IRQ` | ≤ 200 ms `[KẾ THỪA]` | Chưa làm |
| M-13 | Bắt tay tắt máy và thời gian chờ cưỡng bức | Xác định thời gian chờ | Chưa làm |
| M-14 | BMS: ngưỡng cắt sạc, cắt xả, cách khôi phục | Ghi theo hàng đã mua | Chưa làm |
| M-15 | Dòng STOP của MCU (ngoài cảm biến) | < 10 µA `[KẾ THỪA]` | Chưa làm |
| M-16 | I2C chịu tải: 10⁵ giao dịch | Không lỗi | Chưa làm |

## 3. Board CMP và tích hợp

| ID | Phép đo | Tiêu chí | Trạng thái |
|---|---|---|---|
| M-17 | Khởi động từ SD, log console | Có log | Chưa làm |
| M-18 | Nhận camera, chụp ảnh | Ảnh hợp lệ | Chưa làm |
| M-19 | Chất lượng MIPI: ảnh không nhiễu, không mất khung | Không lỗi trong 1 giờ | Chưa làm |
| M-20 | Ghi 720p lên SD | Phát lại được, không hỏng | Chưa làm |
| M-21 | Ảnh đêm 3 m, IR-CUT chuyển | Nhận ra người; chuyển màu đúng | Chưa làm |
| M-22 | Tủ sấy 60 °C, ghi 1 giờ | Không giảm tốc, không tắt | Chưa làm |
| M-23 | Ghi liên tục 7 giờ | Không sụp nguồn; còn dư theo [02](02-thiet-ke-nguon.md) §3 | Chưa làm |
| M-24 | Mất điện đột ngột 100 lần khi đang ghi | Tỷ lệ file hỏng ghi lại; không hỏng hệ thống tệp | Chưa làm |
| M-25 | ESD cơ bản ở cổng USB-C | Không hỏng, không treo | Chưa làm |
| M-33 | Cấp phát danh tính và kết nối MQTT bằng chứng chỉ riêng | Kết nối được, từ chối khi sai | Chưa làm |

## 4. Mẫu ghi kết quả

| ID | Ngày | Rev board | Điều kiện | Dụng cụ | Kết quả | Đạt/Không | Ghi chú |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 5. Xử lý khi không đạt

Ghi vào [10-rui-ro.md](10-rui-ro.md) hoặc nhật ký quyết định, nêu thay đổi thiết kế cần làm; không hạ tiêu chí để vượt qua.
