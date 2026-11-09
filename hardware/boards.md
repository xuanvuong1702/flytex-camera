# Hình học board (sinh tự động)

- Nguồn: `hardware/spec/boards.toml`; kiểm tra: `python -m hardware.geom.cli --check`.
- Đơn vị mm, gốc toạ độ ở góc dưới-trái, nhìn từ trên.

| Board | Kích thước | Diện tích | Lỗ bắt vít | Connector |
|---|---|---|---|---|
| PWR | 100 × 60 × 1.6 | 60.0 cm² | 4 | 6 |
| CMP | 80 × 50 × 1.6 | 40.0 cm² | 4 | 6 |

## PWR

| Connector | x | y | Cạnh | Ghi chú |
|---|---|---|---|---|
| J_USBC | 20.0 | 0.0 | bottom | USB-C chỉ cấp nguồn, chống nước |
| J_PACK | 50.0 | 60.0 | top | BAT+ / BAT-, >= 10 A |
| J_B2B | 70.0 | 30.0 | inside | 2x13 header, xem spec/b2b.toml |
| J_SWD | 93.0 | 15.0 | inside | SWDIO, SWCLK, NRST, GND |
| J_SENS | 7.0 | 35.0 | inside | PIR + 1-Wire |
| J_MEAS | 40.0 | 60.0 | top | Header do dong, jumper mac dinh |

| Lỗ | x | y |
|---|---|---|
| H1 | 5.0 | 5.0 |
| H2 | 95.0 | 5.0 |
| H3 | 5.0 | 55.0 |
| H4 | 95.0 | 55.0 |

## CMP

| Connector | x | y | Cạnh | Ghi chú |
|---|---|---|---|---|
| J_B2B | 55.0 | 25.0 | inside | 2x13 header, xem spec/b2b.toml |
| J_CAM | 10.0 | 50.0 | top | FPC 20 chan |
| J_SD | 65.0 | 50.0 | top | microSD, tiep can khi mo vo |
| J_MODEM | 40.0 | 0.0 | bottom | Header modem, co RI |
| J_CON | 7.0 | 25.0 | inside | UART console |
| J_SVC | 25.0 | 0.0 | bottom | Pad nap dich vu / mux USB |

| Lỗ | x | y |
|---|---|---|
| H1 | 5.0 | 5.0 |
| H2 | 75.0 | 5.0 |
| H3 | 5.0 | 45.0 |
| H4 | 75.0 | 45.0 |

## Kiểm tra tự động

- Đường kính lỗ: 3.2 mm, khe hở 0.5 mm.
- Khoảng cách tối thiểu connector–lỗ: 3.0 mm.
- Cả hai board phải có `J_B2B` và khớp 26 chân của `spec/b2b.toml`.

Đây là bản vẽ khái niệm để chốt vị trí; không phải bản vẽ chế tạo. Gerber cần KiCad và footprint đã kiểm bằng linh kiện thật.
