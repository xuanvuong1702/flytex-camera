# 06 — Cơ khí và nhiệt

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Nhiệt

- Môi trường 40–45 °C, bề mặt vỏ tới khoảng 70 °C `[KẾ THỪA]`.
- Core1106 chỉ định mức −20…+60 °C `[KẾ THỪA]`, nên SoC phải tản qua **vỏ nhôm** bằng miếng dẫn nhiệt. Chưa có mô phỏng hay số đo nào; kiểm chứng bằng tủ sấy 60 °C ở giai đoạn 4 (M-22).
- Pack LFP đặt xa nguồn nhiệt (SoC, boost) và cách nhiệt khỏi mặt vỏ chịu nắng khi có thể.
- NTC cắt sạc dán lên cell, không đặt trên board ([02](02-thiet-ke-nguon.md) §6.3).
- Bộ sạc tuyến tính của prototype tỏa 0,7 W ở 0,5 A: cần diện tích đồng hoặc đường dẫn nhiệt riêng.

## 2. Vỏ

| Giai đoạn | Vỏ |
|---|---|
| Prototype | Hộp nhôm có sẵn hoặc gia công CNC; không làm khuôn |
| Tiền thương mại | Có thể lặp lại CNC hoặc in 3D cho phần phụ |
| Production | Đúc áp lực; chỉ làm khuôn sau khi qua giai đoạn 4 |

Mục tiêu IP65 `[ĐỀ XUẤT]`. Các điểm cần xử lý:

- **Cửa sổ camera:** kính hoặc nhựa trong cho cả ánh sáng thường và hồng ngoại, chống đọng sương. Cần vách ngăn giữa LED IR và ống kính để ánh sáng IR không phản xạ vào ống kính qua cửa sổ.
- **Cửa sổ PIR:** thấu kính Fresnel hoặc vật liệu cho phép hồng ngoại xa đi qua; kính thường chắn PIR.
- **Cân bằng áp suất:** cân nhắc van thoáng khí chống nước.
- **Đường cáp:** gioăng và đầu bịt cho mọi lỗ ra.

## 3. Ăng-ten 4G

Vỏ nhôm chắn sóng. Ăng-ten bên trong vỏ nhôm sẽ yếu đi nhiều. Phương án (O-07):

- ăng-ten gắn ngoài vỏ qua đầu nối chống nước;
- hoặc một phần vỏ bằng nhựa (nắp ăng-ten).

Quyết định sớm vì ảnh hưởng tới hình dạng vỏ và vùng cấm quanh u.FL.

## 4. Cổng USB-C ngoài trời

Cổng sạc là điểm yếu về nước, bụi và ăn mòn. Phương án (O-06):

- receptacle USB-C đạt cấp chống nước (IP67) gắn thẳng lên vỏ;
- nắp đậy có gioăng;
- hoặc cổng nằm trong khoang kín mở bằng vít.

ESD ở cổng: TVS và đường nối đất về vỏ; thử ESD cơ bản ở giai đoạn 4.

## 5. Giao diện cơ khí cần chốt sớm

- Lỗ bắt vít và hình dạng board PWR và CMP.
- Vị trí và kích thước miếng dẫn nhiệt SoC.
- Vị trí camera, PIR, ăng-ten, cổng USB-C.
- Khoang pin và đường dây pack.

Chốt các điểm này giữa vỏ prototype và vỏ production để board không phải thiết kế lại khi đổi vỏ.
