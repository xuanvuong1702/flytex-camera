# 07 — Kế hoạch phát triển

- Trạng thái: v1.1, cập nhật 2026-11-09 theo [13](13-tinh-kha-thi.md)
- Ngày: 2026-11-09

## 1. Nguyên tắc

1. **Đo trước khi vẽ.** Giai đoạn 0 không cần board tự thiết kế.
2. **Mỗi cổng (gate) phải qua mới sang giai đoạn sau.** Không bắt đầu layout board mới khi cổng trước chưa đạt.
3. **Mỗi lần đặt chỉ sửa một board.**
4. **Mọi footprint tự tạo phải qua board thử footprint trước.**
5. Firmware và cloud chạy song song từ giai đoạn 0 trên dev board; phần mềm trong repo này đã sẵn sàng cho việc đó.

## 2. Các giai đoạn

### Giai đoạn 0 — Đo trên dev board (Rev 0)

Dev board Luckfox Pico Max (RV1106) hoặc carrier cho Core1106D + breakout EC200U-EU + module camera + nguồn bench. Danh sách mua và giá ở [13](13-tinh-kha-thi.md) §7.

| Việc | Kết quả | Phép đo |
|---|---|---|
| Đo dòng từng trạng thái (ngủ, ghi, ghi + live, + IR) bằng máy đo dòng ngoài | Bảng công suất thật thay ước tính | M-01, M-02 |
| Đo đỉnh dòng modem khi phát LTE | Chốt ngân sách rail 5 V | M-10, M-36 |
| Xác nhận đường dữ liệu modem qua USB; thử mux hoặc pad nạp dự phòng | Đóng O-01, chốt O-13 | M-34 |
| Ghi 720p bằng bộ mã hóa phần cứng, chọn container | Quyết định ở [04](04-firmware.md) §3.3 | M-20 |
| Thử relay WebRTC (WHEP), đo độ trễ và băng thông | Số đo M-30, M-31, M-39 | |
| Thử eDRX/PSM trên các nhà mạng | Đóng O-09, R-07 | M-32 |
| Thử đánh thức SMS + RI | Đóng A-07, R-24 | M-35 |
| Khảo sát SDK: OTA A/B, nạp SoC, Python trên Buildroot | Đóng O-08, R-29 | |
| Chọn module camera, breakout, pack/BMS | Đóng O-02, O-03, O-04 | M-14, M-37 |
| Đánh giá nhiệt sơ bộ trong tủ sấy | Số liệu cho vỏ | M-22 |

**Cổng G0:** có bảng đo thật thay cho các con số `[ƯỚC TÍNH]`; xác nhận lại 15 Ah (đã chốt D-18) bằng phép đo, chốt camera, breakout, đường nạp và kênh đánh thức. Nếu vi phạm điều kiện dừng ở [13](13-tinh-kha-thi.md) §9.3 thì dừng lại, không xuống tiền làm board.

### Giai đoạn 1 — Board thử footprint

Một board nhỏ chỉ chứa các footprint rủi ro: boost QFN-20, buck SON 1,5×2, IC sạc xung, module Core1106D, FPC camera 20 chân, connector công suất, connector B2B, USB-C, **mux USB (nếu chọn)**. Đặt linh kiện thật lên (bằng tay hoặc PCBA) và đối chiếu bản in 1:1.

**Cổng G1:** mọi footprint khớp linh kiện thật; lỗi nào phát hiện được sửa trong thư viện trước khi vẽ board thật.

### Giai đoạn 2 — Board PWR (Rev A)

Dựng bằng thư viện đã qua G1. Dùng dev board làm máy chủ I2C để thử giao thức MCU ↔ SoC trước khi có CMP. Board Rev A đã dùng **sạc xung có power-path** (D-23), không dùng sạc tuyến tính.

Kiểm: rail, sạc LFP, cắt sạc theo nhiệt, dòng ngủ, bắt tay tắt máy, `MCU_IRQ`, nhiệt khi sạc.

**Cổng G2:** M-04 đến M-16 đạt, cộng M-37, M-38.

### Giai đoạn 3 — Board CMP (Rev B)

Core1106D eMMC, camera, SD, header modem, J_B2B, mux USB/pad dịch vụ. Dùng impedance control cho cặp MIPI do nhà máy tính; route tay MIPI và đường nguồn.

**Cổng G3:** khởi động, camera, ghi 720p, modem truyền dữ liệu, nạp được firmware qua đường dịch vụ.

### Giai đoạn 4 — Tích hợp

Ghép PWR + CMP + MDM + pack 15 Ah + vỏ prototype. Chạy firmware đầy đủ.

**Cổng G4:** ghi 7 giờ ban đêm có IR (M-23), ngủ 24 giờ (M-02), tủ sấy 60 °C (M-22), ba nhà mạng, đánh thức SMS (M-35), sạc, thử ESD cơ bản, mất điện đột ngột 100 lần (M-24), độ trễ live (M-31).

### Giai đoạn 5 — Chuẩn bị production

Quyết định gộp PWR và CMP; rà soát DFM; vỏ production; chứng nhận; lô thí điểm (số lượng TBD). Chọn gauge pin nếu cần phần trăm pin.

## 3. Phụ thuộc

| Quyết định | Cần có trước |
|---|---|
| Dung lượng pack | G0 (bảng công suất) — hiện đã chốt 15 Ah theo tính toán |
| Cách nối modem và đường nạp | G0 (O-13) |
| Layout CMP | Pinout camera, breakout (O-02, O-04) |
| Chọn IC sạc | G0, trước layout PWR (O-05) |
| Vỏ và ăng-ten | Vị trí cổng USB-C, ăng-ten (O-06, O-07) |
| Kênh đánh thức | G0 (O-09, O-12) |
| Gộp board | G4 |

## 4. Đầu ra mỗi giai đoạn

Mỗi cổng kèm: tài liệu cập nhật, kết quả ghi vào [08](08-kiem-chung.md) có ngày, phiên bản board và điều kiện đo, và danh sách việc phát sinh. Kết quả đo nhập vào `tools/measure` để sinh báo cáo, không chép tay nhiều nơi.

## 5. Tiến độ tham khảo

Chi tiết và giả định ở [13](13-tinh-kha-thi.md) §7.3: một kỹ sư toàn thời gian khoảng 9–12 tháng tới lô thí điểm; hai người khoảng 6–8 tháng. Chứng nhận là đường song song, không được để đến G5 mới bắt đầu.
