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
| R1 / R2 | 178 kΩ / 56 kΩ | Đặt ra 5,03 V |
| Rfsw | 267 kΩ | Khoảng 597 kHz |
| Rilim | 64,9 kΩ | Giới hạn khoảng 8,47 A |
| COMP | 10,5 kΩ + 2,2 nF, C8 DNP | Bù vòng |
| L1 | 1,2 µH, Isat ≥ 9 A, che chắn | |

Quy tắc layout cho board mới:

- đặt cuộn cảm và tụ vào sát IC, đường công suất rộng, đồng dày `[ĐỀ XUẤT]`;
- chừa chỗ cho phần tử bù (mạng COMP, phân áp) dưới dạng 0 Ω hoặc DNP để chỉnh trên board;
- không dùng autorouter cho đường công suất.

## 5. Buck 3,3 V

Ứng viên: TPS62840, vì dòng nghỉ cực thấp (xác nhận trong datasheet). Gói SON 1,5×2 mm, 8 pad, **không có pad nhiệt ở giữa** (kết luận của CAM4G v5; tài liệu nguồn của CAM4G còn một chỗ ghi pad EP, nên xác minh lại bằng datasheet `[CHƯA XÁC MINH]`); dùng đúng footprint theo bản vẽ gói DLC của datasheet và đưa vào board thử footprint ([07](07-ke-hoach-phat-trien.md) giai đoạn 1). Dòng ra tối đa 0,75 A `[KẾ THỪA]`. Điện trở đặt áp ra phải kiểm lại trong datasheet cho đúng gói `[CHƯA XÁC MINH]`.

## 6. Sạc USB-C

### 6.1 Cổng và bảo vệ

- CC1 và CC2 mỗi đường nối Rd 5,1 kΩ về GND.
- TVS trên VBUS; PTC hoặc cầu chì tự phục hồi.
- D+ và D− **không nối**. Cổng USB-C chỉ cấp nguồn `[ĐỀ XUẤT]` (D-13). Gỡ lỗi đi qua UART và SWD.

### 6.2 Bộ sạc

**Đổi so với v0.1:** dùng bộ sạc **xung có power-path ngay từ Rev A**, không đợi production. Lý do ở [13](13-tinh-kha-thi.md) F-04: sạc tuyến tính 0,5 A cần 20 giờ cho 10 Ah và 30 giờ cho 15 Ah; tải đấu thẳng VBAT thì pin không bao giờ đầy; tổn hao 1,4 W trong vỏ kín là bài toán nhiệt.

| | Rev A (chốt) | Ghi chú |
|---|---|---|
| Loại | Xung, hỗ trợ LFP 1S, có power-path | Ví dụ LTC4098-3.6 `[CHƯA XÁC MINH]` tình trạng còn hàng; hoặc IC buck-boost lập trình được điện áp sạc 3,6 V |
| Dòng sạc | 1,5–2 A, giảm nếu nguồn yếu | Nguồn USB-C 5 V/2 A; phải đo dòng thực tế của củ sạc |
| Thời gian sạc 15 Ah | ~8–10 giờ | So với 30 giờ của bản tuyến tính |
| Tuyến tính 0,5 A | Chỉ dùng cho board thử trên bàn | Không dùng cho sản phẩm |

Cảnh báo: **không dùng module sạc kiểu TP4056 cho LFP**, vì chúng sạc tới 4,2 V và làm quá áp cell LFP.

Điện áp sạc cuối của bộ sạc phải thấp hơn ngưỡng cắt quá áp của BMS (thường khoảng 3,65 V `[CHƯA XÁC MINH]`).

Điều kiện với pack: BMS phải cho sạc ≥1,5 A; nếu BMS giới hạn 0,5 A thì bộ sạc nhanh cũng vô ích.

### 6.3 Cắt sạc theo nhiệt độ

NTC gắn ở **pack** (sát cell), không đặt trên board, vì board nóng hơn cell. Điểm cắt thực hiện bằng phần cứng, không qua firmware.

Với NTC 10 kΩ B3950 và điện trở kéo 7,15 kΩ (giá trị CAM4G), ngưỡng dưới của chip nằm trong dải 42,5–47,5 % VIN. Tính lại cho **điểm cắt nóng 40,1 °C** và **điểm cắt lạnh 35,1 °C** `[ƯỚC TÍNH]`, không phải đúng 40 °C. Phép tính và bảng nhiệt độ: [pwr-design](../hardware/pwr-design.md) §4. Đo điểm cắt thực bằng tủ sấy (M-05) và chỉnh lại theo NTC của pack thật.

### 6.4 Sạc và tải dùng chung pin

Ở prototype, tải đấu thẳng vào VBAT cùng bộ sạc. Khi camera chạy, dòng từ pin thường lớn hơn dòng sạc 0,5 A, nên pin không đầy và bộ sạc có thể không bao giờ báo xong. Chấp nhận trong prototype dưới dạng "chỉ sạc khi thiết bị nghỉ" và ghi rõ trong tài liệu thử nghiệm. Production dùng power-path để tách tải khỏi pin (O-05).

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
