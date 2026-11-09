# 06 — Cơ khí và nhiệt

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Nhiệt

- Môi trường 40–45 °C, bề mặt vỏ tới khoảng 70 °C `[KẾ THỪA]`.
- Core1106 chỉ định mức −20…+60 °C `[KẾ THỪA]` `[CHƯA XÁC MINH]` cho đúng biến thể, nên SoC phải tản qua **vỏ nhôm** bằng miếng dẫn nhiệt. Chưa có mô phỏng hay số đo nào; kiểm chứng bằng tủ sấy 60 °C ở giai đoạn 4 (M-22).
- Pack LFP đặt xa nguồn nhiệt (SoC, boost) và cách nhiệt khỏi mặt vỏ chịu nắng khi có thể.
- NTC cắt sạc dán lên cell, không đặt trên board ([02](02-thiet-ke-nguon.md) §6.3).
- Bộ sạc tuyến tính của prototype tỏa 0,7 W ở 0,5 A: cần diện tích đồng hoặc đường dẫn nhiệt riêng. **Đã đổi:** Rev A dùng sạc xung có power-path (D-16), nên tổn hao thấp hơn; nhưng vẫn phải đo nhiệt khi sạc 1,5 A (M-38).

### 1.1 Tính sơ bộ, chưa đo

Vỏ 120×80×45 mm có diện tích ngoài khoảng 0,037 m². Với tản tự nhiên + bức xạ ~8 W/m²·K, độ dẫn nhiệt của vỏ khoảng 0,30 W/K. Ở 3,8 W, vỏ nóng hơn môi trường ~13 K; ở 45 °C môi trường là ~58 °C, sát giới hạn 60 °C của module và **chưa tính nắng chiếu trực tiếp** (có thể cộng thêm 10–20 K trên mặt hướng nắng). Đây là lý do [13](13-tinh-kha-thi.md) F-07 xếp nhiệt là rủi ro tiến độ số một.

Biện pháp nếu đo thấy vượt: giảm hiệu năng khi nhiệt cao (720p15), giảm công suất IR, tăng diện tích tản (vỏ có cánh), hoặc tách khoang nóng. Không dùng lỗ thông hơi nếu giữ mục tiêu IP65, trừ khi có màng thoáng khí đúng cấp.

### 1.2 An toàn chạm

Bề mặt kim loại 70 °C là nguy hiểm khi chạm lâu. Phải rà ngưỡng theo tiêu chuẩn an toàn áp dụng (NFR-10) và ghi nhãn cảnh báo; nếu cần, hạ giới hạn công suất để mặt vỏ dưới ngưỡng. Đo bằng M-40.

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

Hình học đã có nguồn sự thật máy đọc được: [hardware/spec/boards.toml](../hardware/spec/boards.toml) sinh ra [bảng kích thước, lỗ và connector](../hardware/boards.md) cùng [bản vẽ SVG](../hardware/drawings/pwr.svg). Đổi vị trí thì sửa spec, chạy `python -m hardware.geom.cli --write`, và cập nhật cả vỏ.

Chốt các điểm này giữa vỏ prototype và vỏ production để board không phải thiết kế lại khi đổi vỏ.
