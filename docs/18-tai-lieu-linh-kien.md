# 18 — Tài liệu linh kiện và đối chiếu thiết kế

- Trạng thái: rà soát v1.0, ngày 2026-11-09
- Nguồn máy đọc: [spec/parts.toml](../spec/parts.toml) → sinh [hardware/parts-register.md](../hardware/parts-register.md)
- Công cụ: `python -m hardware.parts.check --strict` (cổng trước khi mua)

## 1. Cách làm

1. Mỗi linh kiện trong BOM có một mục trong `spec/parts.toml`: MPN, nhà sản xuất, URL datasheet, gói, các thông số then chốt, mức xác minh.
2. Mức xác minh: `yes` = đã mở datasheet và đối chiếu; `partial` = mới một phần; `no` = chưa mở, không được dùng để chốt mua.
3. Bộ kiểm tra đối chiếu từng thông số với yêu cầu thiết kế (dải áp, dòng, nhiệt, gói, chức năng) và bắt buộc mọi MPN quan trọng trong BOM phải có trong sổ.
4. Còn `blocker` thì **không đặt hàng**; `warn` thì ghi nhận và đo/kiểm ở G0.

## 2. Kết quả hiện tại

**14 linh kiện + 4 module ngoài BOM; 6 blocker, 3 cảnh báo.**

### 2.1 Blocker phải đóng trước khi đặt

| Mục | Vấn đề | Cách đóng | Nơi ghi |
|---|---|---|---|
| U2 buck | BOM **không có điện trở hồi tiếp** cho buck chỉnh được; chưa xác minh Vref/gói | Mở datasheet TPS62840: chọn bản cố định 3,3 V nếu có, hoặc thêm 2 điện trở E96 vào BOM; chốt gói DLC (SOT-563) | O-15 |
| U3 sạc | Chưa xác nhận **BQ25798 sạc được LFP 1S 3,6 V** và có power-path | Đọc mục charge voltage + JEITA trong datasheet; nếu không đạt, chuyển ứng viên dự phòng LTC4162-L | O-05 |
| MODEM | Chưa xác nhận **breakout đưa RI ra header** | Kiểm bản vẽ breakout hoặc chọn loại khác; nếu không, kênh Watch SMS không chạy | O-04 |
| SOC | Chưa nạp **bản vẽ 112 chân** Core1106D vào repo | Tải `Core1106D-PinOut.xls` và `Core1106D.pdf` từ tài liệu Luckfox, đối chiếu chân trước khi vẽ CMP | O-11 |
| CAMERA | Chưa chọn module camera và **pinout FPC 20 chân** | Chọn module có IR-CUT + LED IR, lấy datasheet, ghi pinout vào spec | O-02 |
| PACK | Chưa có pack/BMS kèm **UN38.3, IEC 62133, tự tiêu ≤100 µA** | Chọn nhà cung cấp, lấy datasheet và báo cáo; đo tự tiêu bằng PPK2 | O-03 |

### 2.2 Cảnh báo (không chặn đặt, phải đo ở G0)

| Mục | Vấn đề | Xử lý |
|---|---|---|
| MODEM | Đỉnh dòng 2 A là giả định | Đo M-36 bằng shunt + oscilloscope; nếu lớn hơn, tách rail modem hoặc boost lớn hơn |
| J1 USB-C | Receptacle hiện chưa phải loại chống nước | Chốt O-06 (receptacle IP67 hoặc khoang kín có nắp) trước khi làm vỏ |
| L1 cuộn cảm | Isat 9 A chưa xác minh ở 125 °C | Đọc datasheet Vishay, kiểm đường cong Isat theo nhiệt độ |

## 3. Những gì đã đối chiếu và đúng

| Linh kiện | Đã xác nhận | Ghi chú |
|---|---|---|
| TPS61088 | Gói VQFN-20; Vin 2,7–12 V; Vref 1,204 V; Vout tới 12,6 V | Phù hợp boost 5 V/3 A; ILIM/fsw vẫn cần đối chiếu công thức datasheet |
| TPS62840 | Vin 1,8–6,5 V; Iout 0,75 A; Iq 60 nA; **DLC = SOT-563** | Đã sửa sai gói SON 1,5×2 của bản nháp |
| STM32L031G6U6 | **UFQFPN-28**; STOP 0,4 µA; 24 GPIO; −40…85 °C | Đủ chân; thiết kế không phụ thuộc I2C wakeup vì MCU thức khi SoC bật |
| M24C32-FMN6TP | **TSSOP-8**; 1,7–5,5 V; I2C | Đã sửa sai gói SO-8 |
| TPS22918 | 5,5 V; 2 A; Rds(on) ~55 mΩ | Đủ cho +5V_MODEM 1,8 A và +5V_SOC 1,5 A |
| TS3USB221A | USB 2.0 HS; 2 kênh | Dùng cho mux modem/pad nạp (nếu chốt D-20) |
| Core1106D1408 | 1 cổng USB; eMMC 8 GB; 112 chân | Khớp D-19/D-20; thiếu bản vẽ chân |
| EC200U-EU | VBAT 3,3–4,3 V; USB HS | Chưa xác minh đỉnh dòng, RI và eDRX/PSM thực tế |

## 4. Tối ưu và điều chỉnh đề xuất

1. **Buck:** nếu TPS62840 chỉ có bản chỉnh được, thêm cặp điện trở hồi tiếp E96 và ghi giá trị vào [pwr-design](../hardware/pwr-design.md) bằng cách mở rộng `hardware/calc/design.py`. Nếu có bản cố định 3,3 V, chọn bản đó để bớt 2 linh kiện và một nguồn sai số.
2. **Sạc:** BQ25798 là buck-boost 1–4 cell nhưng phải xác nhận ngưỡng sạc thấp nhất 3,6 V và hành vi JEITA. Nếu không đạt, LTC4162-L là ứng viên LFP chuyên dụng, có power-path và lập trình bằng điện trở (bớt phụ thuộc I2C); đổi tốn kém hơn nhưng ít rủi ro hơn.
3. **MCU:** không cần I2C wakeup từ STOP nếu MCU chỉ ngủ khi SoC tắt; khi SoC bật, MCU thức và trả lời I2C. Ghi rõ trong port STM32L0 để người viết không đi tìm tính năng không cần.
4. **B2B:** dòng mỗi chân 1 A của Samtec TSM cần xác nhận trong datasheet; nếu thấp hơn, tăng số chân nguồn hoặc đổi connector.
5. **USB-C:** chốt phương án chống nước trước khi vẽ vỏ, vì nó quyết định khoét vỏ và chiều cao connector.
6. **Đo trước khi tối ưu:** đỉnh modem và dòng ngủ là hai số quyết định kích thước boost/pin; đừng đổi linh kiện trước M-36/M-02.

## 5. Bộ tài liệu cần thu thập (đang thiếu)

| Tài liệu | Cho | Trạng thái |
|---|---|---|
| `Core1106D-PinOut.xls`, `Core1106D.pdf` (Luckfox) | Vẽ CMP, gán chân 112 | **Chưa nạp** |
| EC200U Hardware Design (Quectel) | VBAT, đỉnh dòng, RI, USB | Đã dẫn, chưa trích số |
| BQ25798 datasheet mục charge voltage/JEITA | Chốt sạc LFP | **Chưa đối chiếu** |
| TPS62840 datasheet bản gói DLC | Vref, divider, footprint | Chưa đối chiếu |
| TPS61088 datasheet (ILIM, fsw, COMP) | Chốt giá trị bù | Chưa đối chiếu đầy đủ |
| STM32L031 datasheet + reference manual | STOP, I2C, ADC, chân | Một phần |
| Module camera (SC3336 + IR-CUT) datasheet + pinout | CMP, firmware camera | **Chưa có** |
| Pack/BMS datasheet, UN38.3, IEC 62133, tự tiêu | Mua pack, an toàn | **Chưa có** |
| Antenna datasheet (VSWR, gain, keepout) | Vỏ, RF | **Chưa có** |
| USB-C receptacle IP67 datasheet | Vỏ | **Chưa có** |
| Bản vẽ cơ khí connector (Samtec, Hirose, Amass) | Footprint, 3D | Một phần |

Danh sách việc và thứ tự ưu tiên trước khi mua: [19-truoc-khi-mua.md](19-truoc-khi-mua.md).

## 6. Cách cập nhật

1. Mở datasheet, xác nhận một thông số.
2. Sửa `spec/parts.toml`: `verified`, `source`, giá trị.
3. `python -m hardware.parts.check --write` để sinh lại bảng.
4. `python -m hardware.parts.check --strict` phải hết blocker mới đặt hàng.
5. Ghi ngày và người xác nhận vào cột `source` hoặc `notes`.
