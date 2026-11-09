# 08 — Kiểm chứng

- Trạng thái: v1.1. **Chưa có phép đo nào được thực hiện.** Mọi kết quả trong bảng vẫn là "Chưa làm".
- Ngày: 2026-11-09

Quy tắc: mỗi kết quả ghi ngày, phiên bản board, điều kiện đo, dụng cụ và người đo. Chưa đo thì trạng thái là "Chưa làm", không điền con số. Kết quả nhập vào `tools/measure` và sinh báo cáo bằng công cụ, không chép tay vào nhiều file.

Khoảng số M-26…M-29 để trống (bản nháp v0.1 nhảy số). Giữ nguyên, không đánh số lại vì đã có tham chiếu; phép đo mới bắt đầu từ M-34.

## 1. Giai đoạn 0 — Dev board

| ID | Phép đo | Tiêu chí | Trạng thái |
|---|---|---|---|
| M-01 | Công suất từng trạng thái S0–S3, có và không có IR | Ghi bảng; thay các ước tính ở [02](02-thiet-ke-nguon.md) §3 | Chưa làm |
| M-02 | Dòng ngủ Eco trung bình 24 giờ, **gồm tự tiêu BMS** | < 1 mA (NFR-04) | Chưa làm |
| M-03 | Dòng và độ trễ lệnh của Watch | Ghi lại; so với 5–15 s | Chưa làm |
| M-30 | Băng thông tải lên 4G, ba nhà mạng | ≥ 2 Mbps `[KẾ THỪA]` | Chưa làm |
| M-31 | Độ trễ xem trực tiếp qua relay WebRTC | ≤ 1,5 s `[KẾ THỪA]` | Chưa làm |
| M-32 | eDRX/PSM có được mạng chấp nhận | Ghi theo từng nhà mạng | Chưa làm |
| M-35 | Đánh thức bằng SMS + `MODEM_RI`: độ trễ, dòng, tỷ lệ thành công | 5–30 s, ghi theo mạng | Chưa làm |
| M-36 | Đỉnh dòng modem tại VBAT và tại rail 5 V (shunt + oscilloscope) | Xác định ngân sách F-03 | Chưa làm |
| M-37 | Tự tiêu của BMS trong pack thật, 25 °C | ≤ 100 µA | Chưa làm |
| M-39 | Độ trễ WebRTC và bitrate thích ứng, ba mạng | ≤ 1,5 s ở mức 720p15 | Chưa làm |

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
| M-11 | Hành vi sạc khi tải chạy, có power-path | Tải không lấy từ pin khi đang sạc | Chưa làm |
| M-12 | PIR đánh thức: từ PIR tới `MCU_IRQ` | ≤ 200 ms `[KẾ THỪA]` | Chưa làm |
| M-13 | Bắt tay tắt máy và thời gian chờ cưỡng bức | Xác định thời gian chờ | Chưa làm |
| M-14 | BMS: ngưỡng cắt sạc, cắt xả, cách khôi phục | Ghi theo hàng đã mua | Chưa làm |
| M-15 | Dòng STOP của MCU (ngoài cảm biến) | < 10 µA `[KẾ THỪA]` | Chưa làm |
| M-16 | I2C chịu tải: 10⁵ giao dịch | Không lỗi | Chưa làm |
| M-38 | Nhiệt khi sạc 1,5 A trong vỏ kín, môi trường 45 °C | Vỏ và IC sạc dưới giới hạn | Chưa làm |
| M-40 | Bề mặt vỏ khi nắng chiếu (đèn 1000 W/m² hoặc ngoài trời) | Dưới ngưỡng an toàn chạm (NFR-10) | Chưa làm |

## 3. Board CMP và tích hợp

| ID | Phép đo | Tiêu chí | Trạng thái |
|---|---|---|---|
| M-17 | Khởi động từ SD/eMMC, log console | Có log | Chưa làm |
| M-18 | Nhận camera, chụp ảnh | Ảnh hợp lệ | Chưa làm |
| M-19 | Chất lượng MIPI: ảnh không nhiễu, không mất khung | Không lỗi trong 1 giờ | Chưa làm |
| M-20 | Ghi 720p lên SD | Phát lại được, không hỏng | Chưa làm |
| M-21 | Ảnh đêm 3 m, IR-CUT chuyển | Nhận ra người; chuyển màu đúng | Chưa làm |
| M-22 | Tủ sấy 60 °C, ghi 1 giờ | Không giảm tốc, không tắt | Chưa làm |
| M-23 | Ghi liên tục 7 giờ, ban đêm có IR, pack 15 Ah | Không sụp nguồn; còn dư theo [02](02-thiet-ke-nguon.md) §3 | Chưa làm |
| M-24 | Mất điện đột ngột 100 lần khi đang ghi | Tỷ lệ file hỏng ghi lại; không hỏng hệ thống tệp | Chưa làm |
| M-25 | ESD cơ bản ở cổng USB-C | Không hỏng, không treo | Chưa làm |
| M-33 | Cấp phát danh tính và kết nối MQTT bằng chứng chỉ riêng | Kết nối được, từ chối khi sai | Chưa làm |
| M-34 | Nạp firmware khi modem đang chiếm cổng USB (mux hoặc pad dịch vụ) | Nạp được, không cần tháo modem | Chưa làm |
| M-41 | Chạy bộ test phần mềm trên thiết bị thật (không phải máy tính) | Toàn bộ test pass trên SoC | Chưa làm |

## 4. Mẫu ghi kết quả

Cột khớp với lược đồ CSV của `tools/measure` (`schema.py`) để nhập thẳng bằng công cụ. Tên người đo ghi ở cột Ghi chú; lược đồ CSV không có cột riêng.

| ID | Ngày | Rev board | Điều kiện | Dụng cụ | Đại lượng | Giá trị | Đơn vị | ± % | Đạt/Không | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |

Khi nhập:

- Một phép đo có nhiều đại lượng thì ghi nhiều dòng cùng ID: M-03 cần cả dòng (mA) và độ trễ (s); M-02 ghi dòng trung bình (mA).
- M-32 là boolean: giá trị 1 (mạng chấp nhận) hoặc 0 (không), đơn vị để trống.
- "Chưa đo" là giá trị rỗng + `Đạt/Không = NA`; **không điền 0**.
- Kết quả do công cụ sinh báo cáo, không chép tay sang nhiều file.

## 5. Xử lý khi không đạt

Ghi vào [10-rui-ro.md](10-rui-ro.md) hoặc nhật ký quyết định, nêu thay đổi thiết kế cần làm; không hạ tiêu chí để vượt qua. Nếu vi phạm điều kiện dừng ở [13](13-tinh-kha-thi.md) §9.3, dừng giai đoạn và đánh giá lại kiến trúc.

## 6. Liên kết với công cụ

| Việc | Công cụ |
|---|---|
| Tạo CSV mẫu | `python -m tools.measure.cli sample --out tools/measure/samples/g0-template.csv` |
| Kiểm tra một file đo | `python -m tools.measure.cli check --csv <file>` |
| Ghi kết quả đo | `tools/measure` (CSV 11 cột, có kiểm tra lược đồ) |
| Sinh báo cáo năng lượng | `python -m tools.measure.cli report --csv <file>` |
| Kiểm tra tham chiếu M-xx còn hợp lệ | `python tools/docs_check/check.py` |
| Chạy test phần mềm trước khi lên thiết bị | `python run_tests.py` |

CSV mẫu hiện chỉ có 6 phép đo khởi đầu (M-01…M-03, M-30…M-32). Thêm M-04…M-41 bằng cách thêm dòng cùng 11 cột; không cần sửa mã. Mỗi dòng cần `quantity` và `unit` phù hợp (ví dụ `current`/`mA`, `latency`/`s`, `bandwidth`/`Mbps`); xem danh sách đơn vị hợp lệ trong `tools/measure/schema.py`.

## 7. Số hiệu không dùng

Bản nháp v0.1 nhảy số sau M-25. Giữ các số này ở trạng thái không dùng để tham chiếu cũ không bị hiểu sai; không đánh số lại.

| ID | Lý do |
|---|---|
| M-26 | Không dùng — số bị bỏ trống trong bản nháp v0.1 |
| M-27 | Không dùng — số bị bỏ trống trong bản nháp v0.1 |
| M-28 | Không dùng — số bị bỏ trống trong bản nháp v0.1 |
| M-29 | Không dùng — số bị bỏ trống trong bản nháp v0.1 |
