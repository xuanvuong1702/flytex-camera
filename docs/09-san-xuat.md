# 09 — Sẵn sàng sản xuất

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Quy tắc thiết kế PCB

| Mục | Quy tắc |
|---|---|
| Luật mặc định | Track và khoảng cách ≥ 0,2 mm; chỉ hạ xuống khi một chân linh kiện bắt buộc, và khoanh vùng ngoại lệ |
| Đường công suất | Rộng, đồng dày hoặc plane; route tay, không dùng autorouter |
| MIPI | Impedance control do nhà máy tính; route tay |
| Stackup | Dùng stackup chuẩn của nhà máy |
| Footprint | Ưu tiên thư viện chính thức; mọi footprint tự tạo qua board thử footprint ([07](07-ke-hoach-phat-trien.md) giai đoạn 1) |
| Kiểm tra | DRC sạch **và** đối chiếu bản in 1:1 với linh kiện thật. DRC không bắt được footprint sai |

## 2. BOM

- **Một nguồn duy nhất**: BOM sinh tự động từ schematic. BOM mua hàng là cùng nguồn đó cộng cột phụ, không phải file riêng chỉnh tay (bài học từ CAM4G, [12](12-bai-hoc-tu-cam4g.md)).
- Mỗi dòng: giá trị, footprint, MPN, nhà sản xuất, mã nhà phân phối, nguồn thay thế, vòng đời, ghi chú DNP.
- Ưu tiên linh kiện trong thư viện có sẵn của đơn vị PCBA để giảm phí và lỗi footprint.

## 3. Lắp ráp

- Toàn bộ SMD qua PCBA. Hàn tay chỉ connector xuyên lỗ.
- Fiducial, panel hóa, khoảng trống mép cho máy gắp.
- Tùy chọn DNP có chủ đích (mạng bù, điện trở cấu hình) để chỉnh mà không cần spin board.

## 4. Kiểm tra sản xuất (DFT)

- Test point đủ cho jig kim: rail, SWD, UART, I2C.
- Jig nạp MCU qua SWD; SoC nạp qua thẻ SD hoặc pad riêng `[CHƯA XÁC MINH]`.
- Kịch bản kiểm cuối dây chuyền: rail đúng, đọc `PROTO_VER` qua I2C, UART console có log, camera có hình, modem nhận SIM và đăng ký mạng, ghi số serial và cấp chứng chỉ riêng.

## 5. Giữ và đổi giữa prototype và production

| Hạng mục | Prototype | Production |
|---|---|---|
| SoC | Module Core1106 | Module (chip-down chỉ khi sản lượng đủ lớn) |
| Modem | Breakout EC200U-EU | Module EC200U-EU trực tiếp trên board, giữ nguyên giao diện |
| Sạc | Tuyến tính, sạc khi nghỉ | Xung, có power-path |
| Đo dòng | Header ngoài | Gauge nếu cần phần trăm pin |
| Board | PWR và CMP tách | Quyết định gộp sau G4 |
| Vỏ | Hộp có sẵn / CNC | Đúc áp lực |

## 6. Chứng nhận và tuân thủ

Chưa thực hiện. Chuẩn bị:

- Modem là module đã có chứng nhận; thiết bị cuối vẫn phải được đánh giá theo quy định hiện hành về thiết bị vô tuyến, tương thích điện từ và an toàn tại Việt Nam. Cần hỏi đơn vị thử nghiệm sớm, vì yêu cầu cụ thể chưa được xác minh trong tài liệu này (O-10).
- Pin: yêu cầu nhà cung cấp pack cung cấp báo cáo UN38.3 (vận chuyển) và IEC 62133 (an toàn).
- Giữ hồ sơ linh kiện (datasheet, chứng nhận) cùng BOM.

## 7. Chuỗi cung ứng

Tiêu chí cho module OEM `[KẾ THỪA]`: tài liệu đầy đủ (datasheet, pinout, bản vẽ cơ khí), cam kết còn hàng ≥ 3–5 năm, có đường mua lẻ cho prototype và MOQ rõ cho sản xuất, có phương án thay thế.

| Linh kiện | Rủi ro | Hướng |
|---|---|---|
| Core1106 | Một nguồn cung, phụ thuộc SDK | Đánh giá SDK ở G0; ghi rõ rủi ro khóa nhà cung cấp |
| EC200U-EU | Có thay thế (ví dụ A7670E) | Giữ giao diện modem trung lập |
| Pack LFP | Vận chuyển pin, giấy tờ | Chọn nhà cung cấp có báo cáo |
| Camera | Pinout riêng từng module | Chốt module và pinout trước khi vẽ CMP |

## 8. Chi phí tham khảo

CAM4G ước tính khoảng 120 USD mỗi bộ cho lô 5 bộ (linh kiện board khoảng 34 USD, module và phụ kiện khoảng 87 USD). Đó là tham khảo cho bản đã bỏ một phần linh kiện và chưa phản ánh thiết kế này. Chưa tính lại chi phí cho dự án này.
