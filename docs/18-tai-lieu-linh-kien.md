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

**14 linh kiện + 4 module ngoài BOM; 7 blocker, 3 cảnh báo** (sau khi loại BQ25798).

### 2.1 Blocker phải đóng trước khi đặt

| Mục | Vấn đề | Cách đóng | Nơi ghi |
|---|---|---|---|
| U2 buck | BOM **không có điện trở hồi tiếp** cho buck chỉnh được; chưa xác minh Vref | Mở datasheet TPS62840: chọn bản cố định 3,3 V nếu có, hoặc thêm 2 điện trở E96 vào BOM; gói là **SON-8 1,5×2 (DLC)** | O-15 |
| U3 sạc | **BQ25798 bị loại**: mặc định 1S 4,2 V, watchdog 40 s reset VREG/ICHG; không có I2C master khi SoC tắt | Chọn IC **float 3,6 V bằng phần cứng** + power-path + NTC phần cứng: LTC4162-L, LTC4098-3.6, hoặc CN3058E + ideal diode | O-05 |
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
| TPS62840 | Vin 1,8–6,5 V; Iout 0,75 A; Iq 60 nA; **DLC = SON-8 1,5×2** | Bản CAM4G đúng; lần sửa sang SOT-563 là sai, đã khôi phục |
| STM32L031G6U6 | **UFQFPN-28**; STOP 0,4 µA; 24 GPIO; −40…85 °C | Đủ chân; thiết kế không phụ thuộc I2C wakeup vì MCU thức khi SoC bật |
| M24C32-FMN6TP | **SO-8 150 mil**; 1,7–5,5 V; I2C | Bản CAM4G đúng; lần sửa sang TSSOP-8 là sai, đã khôi phục |
| TPS22918 | 5,5 V; 2 A; Rds(on) ~55 mΩ | Đủ cho +5V_MODEM 1,8 A và +5V_SOC 1,5 A |
| TS3USB221A | USB 2.0 HS; 2 kênh | Dùng cho mux modem/pad nạp (nếu chốt D-20) |
| Core1106D1408 | 1 cổng USB; eMMC 8 GB; 112 chân | Khớp D-19/D-20; thiếu bản vẽ chân |
| EC200U-EU | VBAT 3,3–4,3 V; USB HS | Chưa xác minh đỉnh dòng, RI và eDRX/PSM thực tế |

## 4. Tối ưu và điều chỉnh đề xuất

1. **Buck:** nếu TPS62840 chỉ có bản chỉnh được, thêm cặp điện trở hồi tiếp E96 và ghi giá trị vào [pwr-design](../hardware/pwr-design.md) bằng cách mở rộng `hardware/calc/design.py`. Nếu có bản cố định 3,3 V, chọn bản đó để bớt 2 linh kiện và một nguồn sai số.
2. **Sạc:** BQ25798 **không dùng được** cho kiến trúc này (mặc định 4,2 V, watchdog, không có I2C master khi SoC tắt). Chọn IC float LFP bằng phần cứng; nếu là sạc tuyến tính 1 A thì chấp nhận chậm hơn để đổi lấy an toàn.
3. **MCU:** không cần I2C wakeup từ STOP nếu MCU chỉ ngủ khi SoC tắt; khi SoC bật, MCU thức và trả lời I2C. Ghi rõ trong port STM32L0 để người viết không đi tìm tính năng không cần.
4. **B2B:** dòng mỗi chân 1 A của Samtec TSM cần xác nhận trong datasheet; nếu thấp hơn, tăng số chân nguồn hoặc đổi connector.
5. **USB-C:** chốt phương án chống nước trước khi vẽ vỏ, vì nó quyết định khoét vỏ và chiều cao connector.
6. **Đo trước khi tối ưu:** đỉnh modem và dòng ngủ là hai số quyết định kích thước boost/pin; đừng đổi linh kiện trước M-36/M-02.

## 5. Bộ tài liệu cần thu thập (đang thiếu)

| Tài liệu | Cho | Trạng thái |
|---|---|---|
| `Core1106D-PinOut.xls`, `Core1106D.pdf` (Luckfox) | Vẽ CMP, gán chân 112 | **Chưa nạp** |
| EC200U Hardware Design (Quectel) | VBAT, đỉnh dòng, RI, USB | Đã dẫn, chưa trích số |
| Datasheet IC sạc mới (LTC4162-L / LTC4098-3.6 / CN3058E) | Chốt float, NTC, power-path | **Chưa có** |
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

## 7. Đính chính sau rà soát độc lập 2026-11-09

Rà soát bên ngoài (Ubuntu + gcc 13.3 + datasheet) phát hiện các lỗi mà bộ kiểm tra nội bộ không bắt được:

1. **CI đỏ** vì `regmap.c` thiếu `<stddef.h>`; đã sửa 4 file nguồn + 3 header + 9 file test và thêm lint. Run `42613060903` (commit `08a35e7`) đã **success**.
2. **BQ25798 không an toàn** cho LFP 1S trong kiến trúc này; đã loại, không chỉ "cần xác minh".
3. **Hai đính chính gói ở vòng 1 là sai**: TPS62840 là SON-8 1,5×2, M24C32 là SO-8; đã khôi phục.
4. **NTC 7,15 kΩ** thuộc IC cũ; mục 4 của pwr-design đã tạm hoãn.
5. **+3V3 là 3,0–3,3 V**, không phải 3,3 V cố định.
6. **BOM thiếu linh kiện phụ**; đã thêm các dòng boost/USB/load-switch và đánh dấu phần phụ thuộc IC sạc là `not-chosen`.
7. **Ngưỡng pin LFP và SMS đánh thức** vẫn là blocker chưa sửa; ghi ở [17](17-san-sang-prototype.md) vòng 7.

Bài học: test BOM chỉ kiểm **nhất quán nội bộ**, không chứng minh gói hay thông số đúng datasheet. Mọi `verified=yes` phải kèm nguồn và người kiểm.
