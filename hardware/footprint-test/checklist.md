# Board thử footprint — checklist giai đoạn 1

Mục đích: phát hiện footprint sai **trước** khi đặt board thật. DRC sạch không chứng minh footprint đúng; chỉ linh kiện thật và bản in 1:1 mới chứng minh.

## 1. Linh kiện phải có trên board thử

| # | Footprint | Vì sao rủi ro | Kiểm gì |
|---|---|---|---|
| 1 | Boost QFN-20 (TPS61088 hoặc tương đương) | Pad nhiệt, khoảng cách chân mịn | Hàn được, pad nhiệt đúng, không cầu chì |
| 2 | Buck TPS62840 — **gói chưa chốt**: SOT-563 6 chân (DLC) hay gói khác | Bản nháp CAM4G ghi SON 1,5×2 8 pad; mã DLC là SOT-563 — đúng loại lỗi gói | Mở datasheet, đếm pad, đo pitch, so bản in 1:1; chốt mã gói trước khi vẽ |
| 3 | IC sạc xung (O-05) | Gói và pad chưa biết | Theo datasheet IC được chọn |
| 4 | Module Core1106D 112 chân | Stamp hole, bước chân nhỏ | Bản in 1:1 chồng khít, không lệch chân 1 |
| 5 | FPC camera 20 chân | Pinout riêng từng module | Bản in 1:1, hướng tiếp xúc, chiều dài cáp |
| 6 | Connector B2B 2×13 2,54 mm | Khóa, chống cắm ngược | Cắm thử, có khóa, chân 1 rõ |
| 7 | USB-C receptacle | Chân CC, vỏ, lỗ bắt | Cắm thử, độ bền, chân CC |
| 8 | Mux USB (nếu chọn) | Gói nhỏ, chân mịn | Hàn được, route được |
| 9 | Connector nguồn ≥10 A | Nhiệt, điện trở tiếp xúc | Kích thước dây, khóa |
| 10 | u.FL | Nhỏ, dễ bong | Hàn được, cắm thử |

## 2. Quy trình

1. **Trước khi đặt:** in bản vẽ đồng 1:1 trên giấy, đặt linh kiện thật lên, chụp ảnh. Lệch dưới 0,1 mm mới đạt.
2. **Đặt board thử:** cùng stackup, cùng nhà máy sẽ làm board thật.
3. **Hàn:** đúng quy trình sẽ dùng cho board thật (reflow cho SMD, tay cho xuyên lỗ).
4. **Đo:** từng chân, đặc biệt chân 1 và các chân nguồn; kiểm tra không chập.
5. **Ghi:** mỗi footprint một dòng: đạt/không, sai bao nhiêu, sửa thư viện ở đâu.

## 3. Tiêu chí qua cổng G1

- Mọi footprint trong bảng trên khớp linh kiện thật.
- Bản in 1:1 khớp, không phải chỉnh thư viện sau khi in.
- Không có chân nào phải uốn, cắt, hoặc hàn dây để tiếp xúc.
- Thư viện đã sửa xong và có ảnh chụp làm bằng chứng.
- Mọi lỗi phát hiện được ghi lại, kể cả lỗi nhỏ; không có "chắc không sao".

## 4. Không làm ở giai đoạn này

- Không cố chạy chức năng trên board thử; nó chỉ để kiểm hình học và hàn.
- Không thêm linh kiện không có trong bảng; board thử càng nhỏ càng rẻ.
