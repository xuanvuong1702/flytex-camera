# 12 — Bài học từ CAM4G

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09
- Nguồn: phân tích repo [xuanvuong1702/camera-4G](https://github.com/xuanvuong1702/camera-4G) ngày 2026-11-09 (đã chạy lại test firmware; đọc báo cáo DRC/ERC có sẵn, không chạy lại KiCad).

CAM4G đạt nhiều thứ: schematic ERC sạch, PCB route xong và DRC sạch, Gerber/BOM/CPL, 17 test Python và test host MCU đều pass, và tài liệu ghi rõ cái gì đã và chưa kiểm chứng. Mục này chỉ ghi những gì cần làm khác đi.

## 1. Phần cứng

| # | Quan sát ở CAM4G | Bài học | Áp dụng |
|---|---|---|---|
| 1 | Nhiều lỗi nằm ở footprint và nối chân: land pattern TPS61088 sai, U3 dùng sai gói, Q1–Q3 pad trống do symbol dùng chân chữ còn footprint dùng chân số | DRC sạch không chứng minh footprint đúng | Board thử footprint, bản in 1:1 ([07](07-ke-hoach-phat-trien.md), [09](09-san-xuat.md)) |
| 2 | Shunt 0,05 Ω × 3 A = 150 mV vượt dải ±81,92 mV của INA226 | Phải đối chiếu giới hạn vào/ra của từng chip khi review | Kiểm tra giới hạn là một bước review thiết kế |
| 3 | Mọi track 0,15 mm kể cả đường 5,6 A, cuối cùng phải bù bằng plane | Không gộp đường công suất và tín hiệu mịn trên một board với cùng luật | Tách PWR và CMP ([01](01-kien-truc.md)) |
| 4 | Autorouter bỏ qua một net vì zone toàn board, mất nhiều vòng mới tìm ra | Công cụ tự động cần kiểm tra kết quả; đường quan trọng route tay | [09](09-san-xuat.md) §1 |
| 5 | INA226 không đo được dòng ngủ 0,3 mA (khoảng 3 µV, dưới offset) | Chọn công cụ đo đúng đại lượng cần đo | Header đo dòng ngoài ([02](02-thiet-ke-nguon.md) §8) |
| 6 | NTC cắt sạc trên board, ngưỡng chip có dải 42,5–47,5 % nên điểm cắt thực khoảng 35–40 °C | Đo nhiệt độ đúng chỗ, và đo điểm cắt thật | NTC trên pack, đo M-05 |

## 2. Quy trình và tài liệu

| # | Quan sát ở CAM4G | Bài học | Áp dụng |
|---|---|---|---|
| 7 | BOM mua hàng vẫn ghi giá trị cũ (R7 0,05 Ω 1206, Q3 IRLZ44N, J2 JST XH, U3 WSON) trong khi BOM chính đã sửa; 38 trong 55 dòng chưa có MPN | Đặt hàng theo file này sẽ mua sai đúng các linh kiện vừa sửa | Một BOM sinh từ schematic ([09](09-san-xuat.md) §2) |
| 8 | Tài liệu mâu thuẫn: HANDOVER còn "10/10 test" khi README ghi 17/17; POWER.md ghi shunt 0,05 Ω ở chỗ này và 0,01 Ω ở chỗ khác; test plan sạc 0,9–1,1 A trong khi thiết kế 0,5 A; số lỗi in lụa khác nhau giữa các file | Số liệu lặp lại ở nhiều nơi sẽ trôi | Mỗi con số một nguồn; rà soát ở mỗi cổng |
| 9 | Bảng năng lượng ghi 37 Wh cho 10 Ah, đó là giá trị của 3,7 V; với LFP 3,2 V chỉ 32 Wh. Kịch bản đêm "84 %" của CAM4G, tính lại với giả định dùng được 85 %, là khoảng 98 % | Luôn ghi điện áp danh định khi quy đổi Ah sang Wh | [02](02-thiet-ke-nguon.md) §3 |
| 10 | Mọi con số công suất là ước tính, nhưng nhiều quyết định thiết kế dựa vào chúng | Đo trước khi chốt kiến trúc | Giai đoạn 0 |

## 3. Firmware

| # | Quan sát ở CAM4G | Bài học | Áp dụng |
|---|---|---|---|
| 11 | `hal_enter_stop()` chỉ gọi `WFI`, chưa phải STOP mode; tick 1 ms đánh thức liên tục; PIR đọc bằng polling | Mục tiêu dòng ngủ không đạt được bằng cách này | [04](04-firmware.md) §2.2 |
| 12 | `hal_temp_c()` luôn trả 25; ADC pin quy đổi mà không có hệ số chia áp trong khi LFP có thể 3,65 V | Stub phải lộ ra, không trả giá trị giả | [04](04-firmware.md) §2.2 |
| 13 | Máy trạng thái luôn về ngủ sâu sau khi ghi, không có chế độ Watch như mô tả | Thiết kế và mã phải khớp | [04](04-firmware.md) §3.2 |
| 14 | Vòng chạy chính của ứng dụng Linux chưa nối modem, camera, GPIO; chỉ ghi khung hình giả | "Đã có module" khác "đã chạy hệ thống" | Kiểm thử tích hợp ở G0 |
| 15 | Bộ ghi ghi nối MJPEG thô, không có container dù tài liệu nói có trailer | Mô tả phải khớp mã | [04](04-firmware.md) §3.3 |
| 16 | Tham số timeout của client AT không thực sự giới hạn thời gian đọc; hàng đợi uplink gộp các bản tin trùng nội dung | Mỗi lệnh và bản tin cần thời gian chờ và ID thật | [04](04-firmware.md) §3.4–3.5 |
| 17 | PPP qua UART 921600 baud (khoảng 0,74 Mbps) trong khi mục tiêu live 1–2 Mbps | Kiểm tra băng thông của đường dữ liệu từ đầu | [05](05-ket-noi-va-cloud.md) §1.1 |

## 4. Những gì nên giữ

- Ghi trung thực "đã kiểm chứng" và "chưa kiểm chứng" cạnh nhau.
- Công thức tính nguồn có dẫn nguồn datasheet (ILIM, tần số, bù COMP, phân áp NTC); dùng lại làm điểm khởi đầu, không như chân lý.
- Kiểm thử đơn vị với HAL giả và transport giả cho firmware.
- Rà soát sẵn sàng sản xuất theo bảng lỗi có bằng chứng.
- Tách quyết định phần cứng khỏi tình trạng thương mại (mã LCSC, nhà cung cấp, vỏ).

## 5. Bài học từ chính bản nháp v0.1 của dự án này

Bản nháp v0.1 tránh được nhiều lỗi của CAM4G, nhưng lần rà soát ngày 2026-11-09 tìm ra các lỗi cùng loại, ở mức kiến trúc. Ghi lại để không lặp:

| # | Chuyện gì | Bài học | Sửa ở |
|---|---|---|---|
| 18 | Ghi SoC là "Core1106G3 N256" mà không biết module có mấy cổng USB; thực tế đúng 1 cổng | Đọc datasheet trước khi chốt giả định; một con số sai làm hỏng cả đường nạp firmware | [13](13-tinh-kha-thi.md) F-01, D-20 |
| 19 | Viết "Watch = eDRX + MQTT" trong khi chính tài liệu nói SoC tắt ở Watch | Trước khi ghi một giao thức vào kiến trúc, hỏi: máy nào chạy nó, tốn bao nhiêu điện? | F-02, D-17 |
| 20 | Ghi kịch bản đêm dùng 98 % pin là "gần như không còn dư" và vẫn giữ pack 10 Ah | 98 % không phải là dư; phải có ngưỡng dừng bằng số, không bằng cảm giác | F-05, D-18 |
| 21 | Chọn biến thể module theo RAM (256 MB) mà quên flash; NAND 256 MB không đủ OTA A/B | Kiểm RAM, flash, boot, OTA cùng lúc | F-08, D-19 |
| 22 | Bảng giao thức tự mâu thuẫn: một chỗ little-endian, một chỗ "đọc byte cao chốt byte thấp" | Sinh mã và bảng từ một spec máy đọc được, đừng chép tay | D-23 |

Điểm chung: các lỗi này không nằm ở mạch điện, mà ở **giả định chưa kiểm** được viết thành câu khẳng định. Đó cũng là lý do phần mềm trong repo này được viết kèm test: chỗ nào kiểm được bằng máy thì đừng để bằng lời.
