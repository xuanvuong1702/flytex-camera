# BOM thiết kế (Rev A / Rev B)

Đây là BOM **mức thiết kế** để vẽ schematic và đặt linh kiện mẫu, không phải BOM sản xuất. Cột `verify` cho biết độ tin cậy:

| Giá trị | Nghĩa |
|---|---|
| `candidate` | Đã chọn mã cụ thể nhưng **chưa** đối chiếu tồn kho/giá và chưa kiểm datasheet ở chỗ đánh dấu |
| `verified-datasheet` | Đã đối chiếu datasheet (chưa có trong file này) |
| `not-chosen` | Chưa chọn được mã; không được đặt hàng |
| `dnp` | Có chân trên board nhưng không lắp |

Quy tắc:

1. Mỗi dòng phải có `ref`, `block`, `value`, `qty`, `dnp`, `verify`.
2. `dnp=no` thì `mpn` không được rỗng và `verify` phải là `candidate` hoặc `verified-datasheet`.
3. `dnp=yes` thì được để trống `mpn` nếu `verify=not-chosen`.
4. Số lượng là cho **một board**.
5. File này chưa thay thế BOM sinh từ schematic; khi có KiCad, BOM sẽ sinh tự động và file này chỉ còn là danh sách tham chiếu.

Kiểm tra tự động: `python hardware/bom/tests/test_bom.py`.
