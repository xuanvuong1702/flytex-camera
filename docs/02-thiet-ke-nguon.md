# 02 — Thiết kế nguồn

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09
- Phạm vi: board PWR. Các giá trị linh kiện lấy từ tính toán của dự án CAM4G là *điểm khởi đầu*, chưa kiểm chứng trên phần cứng; phải tính lại trên board mới.
- **Giá trị linh kiện tính toán và kiểm tra tự động** nằm ở [hardware/pwr-design.md](../hardware/pwr-design.md), sinh từ `hardware/calc/`; tài liệu này giữ phần lựa chọn và lý do.

## 1. Cấu trúc

```
USB-C 5V ─► bảo vệ (TVS, PTC) ─► bộ sạc LFP ─► VBAT ◄─► Pack 1S LFP (BMS)
                                                │
                                                ├─► buck ─► +3V3 (MCU, cảm biến)
                                                └─► boost ─► +5V_BOOST ─┬─ SW ─► +5V_SOC
                                                                         └─ SW ─► +5V_MODEM
```

Vì sao vẫn cần boost: LFP 1S chỉ 3,0–3,65 V, trong khi Core1106 cần 4,6–5,2 V `[KẾ THỪA]` và modem breakout lấy 5 V. Vì sao không dùng pack điện áp cao với buck: cổng USB-C 5 V không sạc trực tiếp được pack nhiều cell; muốn vậy phải thêm USB-PD và bộ sạc PD tương thích, trái với kỳ vọng "cắm sạc điện thoại nào cũng được".

## 2. Hai cổng công tắc nguồn 5 V

`+5V_BOOST` đi qua hai công tắc tải riêng để SoC tắt mà modem vẫn sống (chế độ Watch):

| Rail | Cấp cho | Điều khiển |
|---|---|---|
| `+5V_SOC` | CMP: Core1106, camera | MCU |
| `+5V_MODEM` | Header modem trên CMP | MCU |
| `+3V3` | MCU, PIR, 1-Wire, tham chiếu logic | Luôn bật |

Breakout modem cần tụ bulk ≥ 470 µF trên 5 V `[KẾ THỪA]`.

Dòng nghỉ của boost ở tải rất nhẹ ảnh hưởng trực tiếp tới chế độ Watch. `[CẦN ĐO]` Nếu quá cao, phương án dự phòng là một rail riêng cho modem (O-04).

## 3. Ngân sách năng lượng

**Năng lượng của pack.** 10 Ah × 3,2 V danh định = **32 Wh**. Giả định dùng được 85 % → **27,2 Wh** `[ƯỚC TÍNH]`. (Tài liệu CAM4G ghi 37 Wh cho 10 Ah, là giá trị ứng với 3,7 V của pin Li-ion, không đúng với LFP; xem [12](12-bai-hoc-tu-cam4g.md).)

**Công suất theo kịch bản** (lấy từ CAM4G `[KẾ THỪA]` `[ƯỚC TÍNH]`; chưa rõ điểm đo ở phía tải hay phía pin, nên đây là cận dưới):

| Kịch bản | Công suất | 7 giờ | % của 27,2 Wh |
|---|---|---|---|
| Ghi cục bộ | 1,4 W | 9,8 Wh | 36 % |
| Ghi + live 720p | 2,3 W | 16,1 Wh | 59 % |
| Đêm: IR + live 720p | 3,8 W | 26,6 Wh | 98 % |

Công thức: thời gian chạy (h) = Wh dùng được ÷ W.

**Hệ quả.** Kịch bản đêm dùng 98 % năng lượng dùng được. Để có dư 30 % ở kịch bản này cần ≥ 34,6 Wh dùng được, tức khoảng 40,7 Wh danh định, tức khoảng **12,7 Ah**. Pack 15 Ah (48 Wh danh định, 40,8 Wh dùng được) cho dư khoảng 53 %.

`[ĐÃ CHỐT]` (D-18) **Đổi so với v0.1:** pack **15 Ah** ngay từ prototype; 10 Ah chỉ dùng khi thử trên bàn và không dùng để nghiệm thu. Lý do: 98 % không phải là dư, cộng thêm LFP mất 15–20 % dung lượng ở 0 °C và dòng tự tiêu của BMS. Phân tích đầy đủ ở [13](13-tinh-kha-thi.md) F-05. Board PWR thiết kế cho 15 Ah; nếu buộc phải dùng pack nhỏ hơn thì giảm công suất IR ban đêm (PWM hoặc chỉ bật IR khi ghi, không khi live).

**Yêu cầu mới với BMS:** tự tiêu ≤ 100 µA. Dòng này không đi qua header đo của board nhưng vẫn tiêu pin 24/7; BMS 500 µA làm hỏng mục tiêu ngủ sâu ngay từ đầu.

## 4. Boost 5 V

| Thông số | Giá trị | Nhãn |
|---|---|---|
| Vào | 3,0–3,65 V | theo giới hạn BMS |
| Ra | 5,0 V, dải Core1106 4,6–5,2 V | `[KẾ THỪA]` |
| Dòng ra tối đa | 3 A | `[KẾ THỪA]` |
| Dòng vào đỉnh | 5,56 A tại 3,0 V, hiệu suất 90 % | tính lại: 5 × 3 ÷ (3,0 × 0,9) |

**Ngân sách đỉnh chưa khớp.** SoC + camera + thẻ SD đỉnh ~1,5 A, modem Cat-1 quy về 5 V đỉnh ~1,7 A `[CHƯA XÁC MINH]`: tổng 3,2 A > 3 A. Tụ bulk 470 µF trên breakout san được burst ngắn, nhưng nếu boost chạm giới hạn dòng thì 5 V tụt và SoC có thể reset giữa lúc ghi. Phải đo đỉnh modem (M-10) trước khi chốt. Phương án: boost thứ hai cho modem lấy trực tiếp từ VBAT, hoặc boost 3,5–4 A. Chi tiết ở [13](13-tinh-kha-thi.md) F-03.

Ứng viên: TPS61088 (QFN-20). Điểm khởi đầu từ CAM4G, chưa kiểm chứng. Cặp hồi tiếp E96 tính lại cho 5,00 V là 169 kΩ / 53,6 kΩ (sai số 0,00 %); dòng đỉnh cuộn cảm 6,52 A ở 3,0 V, thấp hơn Isat 9 A với dư 38 %. Bảng đầy đủ: [pwr-design](../hardware/pwr-design.md).

| Phần tử | Giá trị | Mục đích |
|---|---|---|
| R1 / R2 | 169 kΩ / 53,6 kΩ | Đặt ra 5,00 V (khớp `pwr-design` và BOM) |
| Rfsw | 267 kΩ | Khoảng 597 kHz |
| Rilim | 64,9 kΩ | Giới hạn khoảng 8,47 A |
| COMP | 10,5 kΩ + 2,2 nF, C8 DNP | Bù vòng |
| L1 | 1,2 µH, Isat ≥ 9 A, che chắn | |

Quy tắc layout cho board mới:

- đặt cuộn cảm và tụ vào sát IC, đường công suất rộng, đồng dày `[ĐỀ XUẤT]`;
- chừa chỗ cho phần tử bù (mạng COMP, phân áp) dưới dạng 0 Ω hoặc DNP để chỉnh trên board;
- không dùng autorouter cho đường công suất.

## 5. Buck 3,3 V

Ứng viên: TPS62840. **Đính chính lần 2, 2026-11-09:** lần sửa trước ghi "DLC = SOT-563 6 chân" là **SAI**. Gói DLC của TPS62840 là **SON-8 1,5×2 mm**; gói 6 chân là bản YBG (WCSP). Bản CAM4G ghi SON-8 là đúng. Bài học: không được "sửa" gói dựa trên suy đoán từ mã đặt hàng khi chưa mở bản vẽ gói trong datasheet. Trước khi vẽ vẫn phải mở datasheet TI, đối chiếu bản vẽ gói DLC, và đưa vào board thử footprint ([07](07-ke-hoach-phat-trien.md) giai đoạn 1) `[CHƯA XÁC MINH]`. Dòng ra tối đa 0,75 A `[KẾ THỪA]`.

**Cách đặt 3,3 V:** TPS62840 dùng **một điện trở VSET nối xuống GND**, không phải cầu phân áp hai điện trở. Bảng VSET trong datasheet cho giá trị theo VOUT; BOM đã có vị trí `R13` nhưng **giá trị chưa chốt** (blocker U2). Trước khi đặt board phải đọc đúng bảng, chọn E96, và kiểm dung sai VOUT. Xem [18](18-tai-lieu-linh-kien.md) §2.1 và O-15.

**Rail +3V3 không cố định 3,3 V.** Buck chỉ hạ áp; khi pin LFP còn 3,0–3,3 V, đầu ra bám theo pin (chế độ 100 % duty), nên rail thực tế là **3,0–3,3 V**. Hệ quả:

- DS18B20 có điện áp tối thiểu 3,0 V → ở pin yếu chỉ còn đúng ngưỡng, phải đo và có thể phải cấp cảm biến từ +5V hoặc dùng buck-boost.
- Mức logic I2C/UART giữa MCU, SoC và breakout modem: mức cao 3,0 V vẫn trên ngưỡng VIH 2,0 V của CMOS 3,3 V, nhưng phải kiểm với breakout dùng mức 1,8 V/3,3 V.
- Nếu đo ở G0 thấy cảm biến hoặc bus không ổn định, đổi sang **buck-boost 3,3 V** (O-16) dù dòng nghỉ cao hơn.

Không được ghi "rail 3,3 V" như một giá trị cố định trong bất kỳ tài liệu nào.

## 6. Sạc USB-C

### 6.1 Cổng và bảo vệ

- CC1 và CC2 mỗi đường nối Rd 5,1 kΩ về GND.
- TVS trên VBUS; PTC hoặc cầu chì tự phục hồi.
- D+ và D− **không nối**. Cổng USB-C chỉ cấp nguồn `[ĐỀ XUẤT]` (D-13). Gỡ lỗi đi qua UART và SWD.

### 6.2 Bộ sạc

**Đã chọn: BQ25070** (Texas Instruments, WSON-10 3×2 mm) — sạc tuyến tính LFP 1S 1 A, **float 3,5 V cố định**, **power-path**, **NTC**, standalone, không cần host hay I2C. Đây là lựa chọn đánh đổi: chậm và nóng hơn sạc xung, nhưng an toàn với LFP và không phụ thuộc firmware.

Yêu cầu cứng rút ra từ lỗi ngày 2026-11-09 (đều thoả):

1. Float LFP đặt bằng phần cứng, không qua thanh ghi.
2. Có power-path để tải chạy từ nguồn vào khi sạc.
3. Không có watchdog buộc phần mềm làm mới cấu hình.
4. Có NTC phần cứng (FR-10).

| Thông số | Giá trị | Ghi chú |
|---|---|---|
| Dòng sạc | **935 mA** | Đặt bằng **11 xung** trên chân CTRL (không phải điện trở). Không gửi xung: 285 mA |
| Float | 3,5 V | Thấp hơn 3,6 V, an toàn hơn; dung lượng nạp được giảm vài % |
| Tổn hao tuyến tính | ~1,4 W ở 935 mA | IC có thermal regulation; phải đo trong vỏ |
| Thời gian sạc 15 Ah | ~12,8 h | Từ 20 % lên đầy ở 935 mA; nếu không gửi xung (>50 h) |

**BQ25798 bị loại**: mặc định 1S 4,2 V/2 A, watchdog 40 s đưa VREG/ICHG/EN_CHG về mặc định, trong khi SoC tắt và MCU không có I2C master — nguy cơ sạc LFP tới 4,2 V. Chi tiết: [18](18-tai-lieu-linh-kien.md).

**CTRL là giao diện xung một dây**, nối tới GPIO MCU (chân `CHG_CTRL`/`CHG_INHIBIT` trên PWR). Firmware gửi 11 xung cao 200 µs, thấp 200 µs rồi giữ thấp 2 ms để chốt 935 mA. Giữ CTRL cao >2 ms là ngắt sạc (dùng cho bảo vệ nhiệt/phần mềm). Không có điện trở đặt dòng; BOM đã bỏ R11.

Việc còn lại của khối sạc: đo dòng thực và điểm cắt NTC ở M-05. Không còn blocker chọn IC hay giá trị.

Cấm dùng module TP4056/TP5100 hay bất kỳ sạc Li-ion 4,2 V cho pack LFP.

### 6.3 Cắt sạc theo nhiệt độ

NTC gắn ở **pack** (sát cell). BQ25070 so V_TS với **12,5 % VLDO** (nóng) và **25 % VLDO** (lạnh), ngắt sạc khi ra ngoài cửa sổ — đường phần cứng, không phụ thuộc firmware.

Mạng đã tính cho NTC 10 kΩ B3950, mục tiêu 0–45 °C: **R1 = 20,0 kΩ** (LDO→TS), **R2 = 8,25 kΩ** (TS→GND), NTC từ TS xuống GND. Kết quả tính: cắt nóng **44,9 °C**, cắt lạnh **−0,6 °C**; xem [pwr-design](../hardware/pwr-design.md) §4. Bảng NTC 7,15 kΩ của CAM4G **không áp dụng**; R5 trong BOM đã đánh dấu DNP.

Đo lại điểm cắt bằng tủ sấy (M-05) với đúng NTC của pack.

### 6.4 Sạc và tải dùng chung pin

BQ25070 có power-path nhưng **dòng qua IN/BAT chỉ tối đa 1,2 A**. Boost 5 V lấy nguồn **trực tiếp từ nút VBAT** (không qua một công tắc hay đường SYS riêng), nên đỉnh 5,56 A ở 3,0 V do **pin cấp**, không do sạc. Khi cắm USB, sạc chia dòng 1,2 A cho tải và pin; nếu tải lớn hơn, pin vẫn xả thêm — chấp nhận vì camera chạy theo sự kiện.

Hệ quả phải ghi trong thử nghiệm: cắm USB không bảo đảm pin đầy nếu camera chạy liên tục; đo M-01/M-02. Không nối boost qua chân BAT của IC sạc.

## 7. Yêu cầu với pack và BMS

| Mục | Yêu cầu |
|---|---|
| Hóa học | LFP 1S, 3,2 V danh định |
| Dung lượng | **15 Ah** (chốt), không nhỏ hơn 10 Ah |
| Dòng xả liên tục của BMS | ≥ 8–10 A, đủ cho đỉnh 5,6 A cộng dư |
| Dòng sạc cho phép của BMS | ≥ 1,5 A, để dùng được bộ sạc xung |
| Tự tiêu của BMS | **≤ 100 µA**, đo ở 25 °C |
| Ngưỡng cắt sạc quá áp | Cao hơn 3,6 V; ghi lại giá trị nhà cung cấp |
| NTC | Có dây NTC kéo ra connector riêng |
| Cắt xả thấp | Khoảng 2–2,5 V; firmware phải tắt hệ thống sớm hơn |
| Khôi phục sau cắt | Nhà cung cấp phải nói rõ cơ chế mở lại (nhiều BMS chỉ mở khi cắm sạc) |
| Giấy tờ | Báo cáo UN38.3 và IEC 62133 |
| Connector | Hai chân công suất ≥ 10 A và hai chân NTC riêng |

## 8. Đo dòng

Không đặt INA226. Thay bằng:

- header 2 chân nối tiếp trên VBAT, dùng để cắm máy đo dòng ngoài (ví dụ Nordic PPK2) hoặc đồng hồ;
- test point trước và sau header.

Lý do: dòng ngủ 0,3 mA qua shunt 0,01 Ω chỉ cho khoảng 3 µV, dưới độ lệch offset của INA226, nên chip này không đo được đúng đại lượng quan trọng nhất. Production nếu cần phần trăm pin: dùng gauge hỗ trợ LFP hoặc bộ đếm coulomb, chọn sau (điện áp LFP rất phẳng nên suy ra phần trăm pin từ điện áp không đáng tin).

## 9. Test point bắt buộc

VBUS, VBAT trước và sau header đo dòng, +5V_BOOST, +5V_SOC, +5V_MODEM, +3V3, GND (nhiều điểm), SW của boost, CHRG, DONE, TEMP, MCU_IRQ, SDA, SCL, SOC_READY, MODEM_STATUS, **MODEM_RI**, **USB_SEL** (nếu dùng mux USB).

## 10. Việc còn mở

- Chọn pack và BMS cụ thể (O-03), với ràng buộc mới: 15 Ah, sạc ≥1,5 A, tự tiêu ≤100 µA.
- Chọn IC sạc xung có power-path cho Rev A (O-05) — không còn để đến giai đoạn 5.
- Đo đỉnh dòng của modem (M-10) và dòng nghỉ của boost/breakout ở Watch (R-04).
- ADC đo pin: điện áp LFP có thể tới 3,65 V, cao hơn rail 3,3 V, nên mạch chia áp là bắt buộc. Phương án 100 kΩ/100 kΩ cho 1,825 V ở ADC và 1,61 mV/LSB `[ĐỀ XUẤT]`, xem [pwr-design](../hardware/pwr-design.md) §5.
- Nếu chọn mux USB: chọn mux và cách điều khiển `USB_SEL` (O-13).
