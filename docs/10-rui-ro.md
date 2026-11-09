# 10 — Sổ rủi ro

- Trạng thái: v1.1, cập nhật sau phân tích khả thi [13](13-tinh-kha-thi.md)
- Ngày: 2026-11-09
- Mức: T thấp, TB trung bình, C cao. Đánh giá ban đầu, chưa có số đo.

Các dòng R-20…R-30 là rủi ro mới phát hiện trong lần rà soát này; R-03, R-04, R-06, R-10, R-12 đã được nâng mức.

| ID | Rủi ro | Xác suất | Ảnh hưởng | Giảm thiểu | Xử lý ở |
|---|---|---|---|---|---|
| R-01 | Footprint sai khiến board không hàn được hoặc không chạy | C | C | Board thử footprint, đối chiếu bản in 1:1 | G1 |
| R-02 | Boost 5 V/3 A kém ổn định do layout (cuộn cảm, tụ) | TB | C | Board PWR riêng, route tay, chừa tùy chọn bù | G2 |
| R-03 | **Pack thiếu cho 7 giờ ban đêm** (nâng từ TB/TB) | **C** | **C** | Chốt 15 Ah, đo M-01, giới hạn IR, tính cả lạnh và tự tiêu BMS | G0, G4 |
| R-04 | Dòng ngủ vượt mục tiêu (boost, breakout modem, BMS) | **C** | **C** | Đo từng khối (M-09, M-10, M-37); rail riêng cho modem | G0, G2 |
| R-05 | Breakout modem thiếu USB, hạ áp hoặc đổi mức | TB | TB | Chọn theo danh sách [05](05-ket-noi-va-cloud.md) §1.2 | G0 |
| R-06 | **Một cổng USB: modem chiếm, không nạp được firmware** (nâng từ TB/TB) | **C** | **C** | Mux USB hoặc pad dịch vụ + đường nạp qua SD; M-34 | G0, G3 |
| R-07 | Nhà mạng không hỗ trợ eDRX/PSM, Watch tốn pin hơn nhiều | TB | C | Thử ba nhà mạng; phương án SMS-only hoặc poll | G0 |
| R-08 | Vỏ nhôm che sóng 4G | C | C | Ăng-ten ngoài hoặc nắp nhựa | G0, G4 |
| R-09 | Cổng USB-C ngoài trời bị nước, bụi, ESD | TB | TB | Receptacle chống nước, nắp, TVS | G4 |
| R-10 | **Sạc chậm/không đầy pin** (nâng từ T/T) | **C** | **TB** | Sạc xung có power-path từ Rev A; đo M-04, M-11 | G2 |
| R-11 | BMS cắt đột ngột hỏng dữ liệu SD hoặc khó khôi phục | TB | TB | Firmware tắt sớm; hỏi rõ cơ chế mở lại | G2 |
| R-12 | **SoC quá nhiệt ở 60 °C trong vỏ kín** (nâng từ TB/C) | **C** | **C** | Tản qua vỏ, thử tủ sấy và nắng, giảm hiệu năng theo nhiệt | G4 |
| R-13 | Ảnh nhiễu do MIPI | TB | TB | Impedance control, route tay, chiều dài cân bằng | G3 |
| R-14 | SDK Core1106 thiếu OTA hoặc bộ mã hóa phần cứng dùng được | TB | C | Đánh giá ở G0 | G0 |
| R-15 | Số liệu trong tài liệu mâu thuẫn, trôi khỏi thực tế | TB | TB | Spec máy đọc + CI kiểm; rà soát ở mỗi cổng | mọi G |
| R-16 | Yêu cầu chứng nhận và quy định tại Việt Nam chưa rõ | TB | C | Hỏi đơn vị thử nghiệm sớm, trước khi làm vỏ | G0, G5 |
| R-17 | Pack không có giấy tờ vận chuyển, an toàn | TB | TB | Chọn nhà cung cấp có UN38.3, IEC 62133 | G0 |
| R-18 | Đường dữ liệu modem qua UART không đủ băng thông | **T** | TB | Đã chốt USB cho dữ liệu; còn phụ thuộc R-06 | G0 |
| R-19 | Điểm cắt sạc theo nhiệt lệch khỏi 40 °C | C | TB | Đo bằng tủ sấy, chỉnh theo NTC của pack thật | G2 |
| R-20 | BMS tự tiêu cao (50–500 µA) làm hỏng mục tiêu ngủ sâu | C | TB | Yêu cầu ≤100 µA, đo M-37, đổi pack nếu không đạt | G0 |
| R-21 | Kênh đánh thức SMS: mạng không cấp eDRX, SMS đến trễ hoặc tốn phí mỗi lần | TB | TB | Thử ba mạng (M-35), phương án TCP poll nếu O-12 đóng được, tính phí vào giá dịch vụ | G0 |
| R-22 | Chọn sai biến thể module (NAND 256 MB thay vì eMMC) | TB | C | Chốt eMMC 8 GB (D-22) trước khi mua | G0 |
| R-23 | Sạc nhanh 1,5 A làm nóng vỏ và IC sạc trong vỏ kín | TB | TB | Đo M-38, giảm dòng sạc khi nhiệt cao, tản nhiệt cho IC | G2 |
| R-24 | Boost 3 A không đủ khi modem burst đồng thời ghi hình | TB | C | Đo M-36, tách rail modem hoặc boost lớn hơn | G0, G2 |
| R-25 | Relay/WebRTC không đạt 1,5 s hoặc Cat-1 không đủ băng thông | TB | TB | Đo M-31, M-39; bitrate thích ứng; hạ mục tiêu độ phân giải chứ không hạ tiêu chí trễ | G0 |
| R-26 | Nhiệt bề mặt vỏ gây bỏng hoặc không đạt an toàn | TB | TB | Đo M-40, giới hạn công suất, nhãn cảnh báo, thiết kế vỏ | G4 |
| R-27 | Python trên Buildroot chiếm quá nhiều flash/RAM hoặc SDK không có | TB | TB | Kiểm ở G0 (R-29), phương án chuyển sang C/C++ nếu cần | G0 |
| R-28 | Nhà cung cấp Core1106D ngừng bán hoặc đổi chân | T | C | Mua tồn cho lô thí điểm, giữ CMP tách rời, tìm module thay thế chân tương thích | G5 |
| R-29 | SDK Core1106 không hỗ trợ OTA A/B hoặc không có RK MPI ổn định | TB | C | Đánh giá SDK ở G0; nếu thiếu, OTA chỉ còn cách tải image vào thẻ | G0 |
| R-30 | Tài liệu sinh và tài liệu người viết lệch nhau | TB | T | CI chạy `spec/generate.py --check` và `tools/docs_check` | mọi G |
| R-31 | MCU reset (watchdog, brown-out) trong khi SoC đang chạy: `fly_init` cắt `+5V_SOC` ngay, có thể hỏng thẻ/FS | TB | C | Giữ nguồn bằng mạch hoặc cờ "SoC đang chạy" trong NVM trước khi coi là an toàn; thử M-24 | G2, G4 |
| R-32 | IWDG trên STM32L0 vẫn đếm trong STOP; nếu bật watchdog khi ngủ dài sẽ reset thiết bị | TB | C | Chốt phương án ở port: tắt IWDG trước STOP và bật lại sau, hoặc thức định kỳ ngắn để kick; đo ảnh hưởng lên dòng ngủ (M-02) | G2 |
