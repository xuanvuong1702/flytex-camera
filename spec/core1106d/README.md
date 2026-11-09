# Nguồn dữ liệu chân Core1106D (nhập từ tài liệu Luckfox)

- Nguồn: `Core1106D-PinOut.xls` tại
  https://raw.githubusercontent.com/LuckfoxTECH/Luckfox-Pico-docs/main/Hardware/Schematic/Core1106D-PinOut.xls
- Ngày nhập: 2026-11-09; 112 chân, cùng định nghĩa với Core1106.
- `pins.csv` giữ nguyên thứ tự và tên chân của nhà sản xuất; không sửa tay.
- Cột `io_power` là miền nguồn IO (1,8 V hoặc 3,3 V) — **không** phải nguồn cấp cho module.
- Khi vẽ CMP: chỉ nối các chân đã có trong `pins.csv`; nếu cần đổi chức năng, ghi vào
  bảng ánh xạ của CMP và cập nhật tài liệu này bằng bản XLS mới.

Kiểm tra: `python spec/tests/test_core1106d.py`.