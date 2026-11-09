# 07 — Kế hoạch phát triển

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Nguyên tắc

1. **Đo trước khi vẽ.** Giai đoạn 0 không cần board tự thiết kế.
2. **Mỗi cổng (gate) phải qua mới sang giai đoạn sau.** Không bắt đầu layout board mới khi cổng trước chưa đạt.
3. **Mỗi lần đặt chỉ sửa một board.**
4. **Mọi footprint tự tạo phải qua board thử footprint trước.**
5. Firmware và cloud chạy song song từ giai đoạn 0 trên dev board.

## 2. Các giai đoạn

### Giai đoạn 0 — Đo trên dev board (Rev 0)

Dev board Core1106 (ví dụ loại Pico Max mà CAM4G đã tham khảo) + breakout EC200U-EU + module camera + nguồn bench.

| Việc | Kết quả |
|---|---|
| Đo dòng từng trạng thái (ngủ, ghi, ghi + live, + IR) bằng máy đo dòng ngoài | Bảng công suất thật thay cho ước tính |
| Xác nhận đường dữ liệu modem qua USB; số cổng USB của Core1106 | Đóng O-01, quyết định D-07, D-13 |
| Ghi 720p bằng bộ mã hóa phần cứng, chọn container | Quyết định ở [04](04-firmware.md) §3.3 |
| Thử relay video qua 4G, đo độ trễ và băng thông | Số đo M-30, M-31 |
| Thử eDRX/PSM trên các nhà mạng | Đóng R-07 |
| Khảo sát SDK: OTA, nạp SoC | Đóng O-08 |
| Chọn module camera và breakout | Đóng O-02, O-04 |
| Chọn pack và BMS | Đóng O-03 |
| Đánh giá nhiệt sơ bộ trong tủ sấy | Số liệu cho vỏ |

**Cổng G0:** có bảng đo thật; chốt dung lượng pack (10 hay 15 Ah), camera, breakout, và phương án modem USB/UART.

### Giai đoạn 1 — Board thử footprint

Một board nhỏ chỉ chứa các footprint rủi ro: boost QFN-20, buck SON 1,5×2, module Core1106, FPC camera 20 chân, connector công suất, connector B2B, USB-C. Đặt linh kiện thật lên (bằng tay hoặc PCBA) và đối chiếu bản in 1:1.

**Cổng G1:** mọi footprint khớp linh kiện thật; lỗi nào phát hiện được sửa trong thư viện.

### Giai đoạn 2 — Board PWR (Rev A)

Dựng bằng thư viện đã qua G1. Dùng dev board làm máy chủ I2C để thử giao thức MCU ↔ SoC trước khi có CMP.

Kiểm: rail, sạc LFP, cắt sạc theo nhiệt, dòng ngủ, bắt tay tắt máy, `MCU_IRQ`.

**Cổng G2:** M-04 đến M-16 đạt ([08](08-kiem-chung.md)).

### Giai đoạn 3 — Board CMP (Rev B)

Core1106, camera, SD, header modem, J_B2B. Dùng impedance control cho cặp MIPI do nhà máy tính; route tay MIPI và đường nguồn.

**Cổng G3:** khởi động, camera, ghi 720p, modem truyền dữ liệu.

### Giai đoạn 4 — Tích hợp

Ghép PWR + CMP + MDM + pack + vỏ prototype. Chạy firmware đầy đủ.

**Cổng G4:** ghi 7 giờ, ngủ 24 giờ, tủ sấy 60 °C, ba nhà mạng, sạc, thử ESD cơ bản, mất điện đột ngột 100 lần không hỏng dữ liệu.

### Giai đoạn 5 — Chuẩn bị production

Quyết định gộp PWR và CMP; chọn chip sạc xung và power-path; rà soát DFM; vỏ production; chứng nhận; lô thí điểm (số lượng TBD).

## 3. Phụ thuộc

| Quyết định | Cần có trước |
|---|---|
| Dung lượng pack | G0 (bảng công suất) |
| Cách nối modem (USB/UART) | G0 (O-01) |
| Layout CMP | Pinout camera, breakout (O-02, O-04) |
| Vỏ và ăng-ten | Vị trí cổng USB-C, ăng-ten (O-06, O-07) |
| Gộp board | G4 |

## 4. Đầu ra mỗi giai đoạn

Mỗi cổng kèm: tài liệu cập nhật, kết quả ghi vào [08](08-kiem-chung.md) có ngày, phiên bản board và điều kiện đo, và danh sách việc phát sinh.
