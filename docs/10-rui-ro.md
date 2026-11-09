# 10 — Sổ rủi ro

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09
- Mức: T thấp, TB trung bình, C cao. Đánh giá ban đầu, chưa có số đo.

| ID | Rủi ro | Xác suất | Ảnh hưởng | Giảm thiểu | Xử lý ở |
|---|---|---|---|---|---|
| R-01 | Footprint sai khiến board không hàn được hoặc không chạy | C | C | Board thử footprint, đối chiếu bản in 1:1 | G1 |
| R-02 | Boost 5 V/3 A kém ổn định do layout (cuộn cảm, tụ) | TB | C | Board PWR riêng, route tay, chừa tùy chọn bù | G2 |
| R-03 | Pin 10 Ah thiếu cho 7 giờ ban đêm có IR và live | C | TB | Đo ở G0, thiết kế cho tới 15 Ah, giới hạn IR | G0 |
| R-04 | Dòng ngủ vượt mục tiêu (boost, breakout modem, rò) | TB | C | Đo từng khối; có phương án rail riêng cho modem | G0, G2 |
| R-05 | Breakout modem thiếu USB, hạ áp hoặc đổi mức | TB | TB | Chọn theo danh sách yêu cầu ([05](05-ket-noi-va-cloud.md) §1.2) | G0 |
| R-06 | Core1106 chỉ có một cổng USB, xung đột với nạp firmware | TB | TB | Xác minh sớm; USB-C chỉ cấp nguồn | G0 |
| R-07 | Nhà mạng không hỗ trợ eDRX/PSM, chế độ Watch tốn pin hơn nhiều | TB | C | Thử ba nhà mạng; phương án poll | G0 |
| R-08 | Vỏ nhôm che sóng 4G | C | C | Ăng-ten ngoài hoặc nắp nhựa | G0, G4 |
| R-09 | Cổng USB-C ngoài trời bị nước, bụi, ESD | TB | TB | Receptacle chống nước, nắp, TVS | G4 |
| R-10 | Sạc khi camera chạy không đầy pin ở prototype | C | T | Ghi nhận giới hạn; power-path ở production | G2, G5 |
| R-11 | BMS cắt đột ngột hỏng dữ liệu SD hoặc khó khôi phục | TB | TB | Firmware tắt sớm; hỏi rõ cơ chế mở lại | G2 |
| R-12 | SoC quá nhiệt ở 60 °C | TB | C | Tản qua vỏ, thử tủ sấy | G4 |
| R-13 | Ảnh nhiễu do MIPI | TB | TB | Impedance control, route tay, chiều dài cân bằng | G3 |
| R-14 | SDK Core1106 thiếu OTA hoặc bộ mã hóa phần cứng dùng được | TB | C | Đánh giá ở G0 | G0 |
| R-15 | Số liệu trong tài liệu mâu thuẫn, trôi khỏi thực tế | C | TB | Mỗi con số một nguồn; rà soát ở mỗi cổng | mọi G |
| R-16 | Yêu cầu chứng nhận và quy định tại Việt Nam chưa rõ | TB | C | Hỏi đơn vị thử nghiệm sớm | G5 |
| R-17 | Pack không có giấy tờ vận chuyển, an toàn | TB | TB | Chọn nhà cung cấp có UN38.3, IEC 62133 | G0 |
| R-18 | Đường dữ liệu modem qua UART không đủ băng thông | C | TB | Dùng USB cho dữ liệu; xác minh | G0 |
| R-19 | Điểm cắt sạc theo nhiệt lệch khỏi 40 °C | C | TB | Đo bằng tủ sấy, chỉnh theo NTC của pack thật | G2 |
