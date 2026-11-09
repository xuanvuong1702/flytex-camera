# Phần cứng

Trạng thái: **chưa có schematic, chưa có board.** Thư mục này chứa những gì có thể chuẩn bị trước khi vẽ: danh sách mua cho giai đoạn 0, checklist board thử footprint, và hợp đồng chân đã chốt.

## Nguyên tắc

1. Không vẽ board trước khi qua G0 ([07](../docs/07-ke-hoach-phat-trien.md)).
2. Mọi chân của J_B2B đến từ [spec/b2b.toml](../spec/b2b.toml); không chép tay sang schematic rồi sửa một phía.
3. Mọi footprint tự tạo phải qua board thử footprint trước khi đặt board thật ([footprint-test](footprint-test/checklist.md)).
4. DRC sạch không chứng minh footprint đúng: phải đối chiếu bản in 1:1 với linh kiện thật.

## Nội dung

| File | Dùng cho |
|---|---|
| [g0-bom.md](g0-bom.md) | Danh sách mua cho giai đoạn 0, có ghi rõ cái gì phải xác minh |
| [pwr-design.md](pwr-design.md) | **Sinh tự động** từ `calc/`: giá trị linh kiện, dòng đỉnh, điểm cắt NTC, nhiệt, và bảng kiểm tra đạt/không |
| [netlist/](netlist/) | Netlist pin-level PWR, ERC net và bảng chân |
| [kicad/](kicad/) | Thư viện ký hiệu KiCad cho IC nguồn, sinh từ bảng chân datasheet |
| [schematic/](schematic/) | Schematic khối PWR/CMP (SVG) + kiểm tra net |
| [boards.md](boards.md) | **Sinh tự động** từ `spec/boards.toml`: kích thước, lỗ bắt vít, vị trí connector |
| [drawings/](drawings/) | Bản vẽ SVG nhìn từ trên của PWR và CMP |
| [bringup.md](bringup.md) | Quy trình bật board lần đầu, có điểm dừng |
| [bom/](bom/) | BOM mức thiết kế cho PWR Rev A và CMP Rev B, có trạng thái xác minh |
| [calc/](calc/) | Phép tính thiết kế + test; `python -m hardware.calc.cli --check` |
| [geom/](geom/) | Hình học + sinh bản vẽ; `python -m hardware.geom.cli --check` |
| [footprint-test/checklist.md](footprint-test/checklist.md) | Board thử footprint (giai đoạn 1) |
| [../spec/generated/b2b.md](../spec/generated/b2b.md) | Pinout J_B2B sinh tự động, có kiểm dòng |
| [../spec/generated/pinout_pwr_cmp.csv](../spec/generated/pinout_pwr_cmp.csv) | Cùng dữ liệu, dạng CSV để nhập EDA |

## Chưa có, có chủ đích

- Schematic PWR/CMP: cần pinout camera (O-02), breakout (O-04), IC sạc (O-05) trước.
- Footprint: chỉ tạo sau khi có linh kiện thật trong tay, để đo bằng thước và bản in 1:1.
- Stackup: dùng stackup chuẩn của nhà máy, chốt khi đặt board.
