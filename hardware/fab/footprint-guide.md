# Cách lấy/kiểm footprint chính xác

Mục tiêu: có footprint đúng **pad, pitch, body, thermal pad, khoảng cách** trước khi layout. Không dùng footprint "gần giống" cho board thật.

## 1. Nguồn ưu tiên

| Nguồn | Dùng cho | Cách lấy |
|---|---|---|
| **Datasheet hãng** | TPS62840 DLC, BQ25070 DQC | Mở mục *Package Drawing / Mechanical Data*; vẽ pad theo land pattern. |
| **Samtec** | SSM-113-L-DV, TSM-113-01-L-DV | Trang sản phẩm → *Drawing* / *Build-A-Part*; lấy recommended PCB layout. |
| **Luckfox** | Core1106D 112-pin | Wiki + schematic PDF; yêu cầu FAE gửi CAD/STEP/board outline. Module 30×30 mm, 112 castellated holes. |
| **Hirose** | FH12-20S-0.5SH | KiCad đã có đúng: `Connector_FFC-FPC:Hirose_FH12-20S-0.5SH_1x20-1MP_P0.50mm_Horizontal`. |
| **SnapEDA / Ultra Librarian / SamacSys** | Tất cả IC | Tải `.kicad_mod` + `.step`; luôn đối chiếu datasheet. |
| **LCSC/EasyEDA** | Linh kiện phổ thông | Chuyển footprint sang KiCad; kiểm pad/pitch. |

## 2. Từng linh kiện còn thiếu

### TPS62840 DLC (SON-8 1.5×2 mm)
- Datasheet: <https://www.ti.com/lit/ds/symlink/tps62840.pdf>
- Xem *DLC (S-PVSON-N8)*: 8 pad, pitch 0.5 mm, body 1.5×2 mm, có/không thermal pad tùy package.
- KiCad có `Package_SON:VSON-8_1.5x2mm_P0.5mm` gần đúng; **phải kiểm pad width/length và pad 1** với bản vẽ TI trước khi dùng.

### BQ25070 DQC (WSON-10 3×2 mm)
- Datasheet: <https://www.ti.com/lit/ds/symlink/bq25070.pdf>
- Xem *DQC (S-PWSON-N10)*: 10 pad + thermal pad, pitch 0.5 mm.
- Không có trong KiCad; phải vẽ mới hoặc tải từ SnapEDA/TI CAD.

### Samtec SSM-113-L-DV / TSM-113-01-L-DV
- <https://www.samtec.com/products/ssm-113-l-dv>
- <https://www.samtec.com/products/tsm-113-01-l-dv>
- Lấy bản vẽ recommended footprint; chú ý hàng 2×13, pitch 2.54, chiều dài pad và keep-out.
- KiCad `PinSocket_2x13_P2.54mm_Vertical` / `PinHeader_2x13_P2.54mm_Vertical` chỉ đúng lưới chân, **không đảm bảo đúng Samtec**.

### Core1106D 112-pin
- <https://wiki.luckfox.com/Core1106D/Pinout/>
- Schematic PDF: <https://raw.githubusercontent.com/LuckfoxTECH/Luckfox-Pico-docs/main/Hardware/Schematic/Core1106D.pdf>
- Module 30×30 mm, 112 castellated holes; cần bản vẽ outline/pad từ Luckfox (hoặc đo mẫu thật).
- Footprint phải có pad castellation, keep-out antenna/Wi-Fi, lỗ định vị nếu có.

### Service pad / test point 4 chân
- Tự vẽ: 4 pad 1.5 mm, pitch 2.54 mm, lỗ xuyên 0.8 mm; hoặc dùng 4 test point đơn.
- Không cần footprint phức tạp, nhưng phải có silk + keep-out.

## 3. Quy trình tạo trong KiCad

1. Mở **Footprint Editor** → New Footprint.
2. Đặt pad theo bản vẽ: số hiệu, shape, size, drill, pitch, thermal pad + via.
3. Vẽ courtyard = body + 0.25 mm mỗi bên; fab layer = body; silk = outline.
4. Gán 3D model `.step` nếu có.
5. Lưu vào thư viện riêng `flytex-footprints.pretty`.
6. Kiểm:
   - Đếm pad = số chân.
   - In 1:1, đặt linh kiện thật lên giấy/soi.
   - Soi pad 1 và hướng chân với datasheet.
   - Chạy DRC trên board thử với footprint.
7. Ghi nguồn + ngày + người kiểm vào `hardware/fab/footprint-register.md`.

## 4. Kiểm tra trước khi layout

- [ ] Đúng số pad, pitch, body.
- [ ] Pad 1 đúng góc.
- [ ] Thermal pad + via đúng.
- [ ] Courtyard không đè linh kiện khác.
- [ ] 3D model khớp.
- [ ] Có trong thư viện dự án, không phụ thuộc lib ngoài.
- [ ] Đã in 1:1 và đối chiếu mẫu thật (nếu có).

Không đạt các mục trên thì **không layout**, vì sửa footprint sau khi route sẽ phải làm lại.
