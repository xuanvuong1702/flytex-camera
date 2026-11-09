# 02 — Thiết kế nguồn

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09
- Phạm vi: board PWR. Các giá trị linh kiện lấy từ tính toán của dự án CAM4G là *điểm khởi đầu*, chưa kiểm chứng trên phần cứng; phải tính lại trên board mới.

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

**Hệ quả.** Kịch bản đêm cuối cùng gần như không còn dư. Để có dư 30 % ở kịch bản này cần ≥ 34,6 Wh dùng được, tức khoảng 40,7 Wh danh định, tức khoảng **12,7 Ah**. Pack 15 Ah (48 Wh danh định, 40,8 Wh dùng được) cho dư khoảng 53 %.

`[ĐỀ XUẤT]` Thiết kế board PWR (connector, dòng, nhiệt) cho pack tới 15 Ah; prototype dùng 10 Ah. Chốt dung lượng sau khi đo ở giai đoạn 0 ([07](07-ke-hoach-phat-trien.md)). Phương án khác: giới hạn công suất IR ban đêm.

## 4. Boost 5 V

| Thông số | Giá trị | Nhãn |
|---|---|---|
| Vào | 3,0–3,65 V | theo giới hạn BMS |
| Ra | 5,0 V, dải Core1106 4,6–5,2 V | `[KẾ THỪA]` |
| Dòng ra tối đa | 3 A | `[KẾ THỪA]` |
| Dòng vào đỉnh | 5,56 A tại 3,0 V, hiệu suất 90 % | tính lại: 5 × 3 ÷ (3,0 × 0,9) |

Ứng viên: TPS61088 (QFN-20). Điểm khởi đầu từ CAM4G, chưa kiểm chứng:

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

| | Prototype | Production |
|---|---|---|
| Loại | Tuyến tính LFP 3,6 V (ví dụ CN3058E) | Xung, hỗ trợ LFP, có power-path |
| Dòng sạc | ≤ 0,5 A | 1–1,5 A `[ĐỀ XUẤT]` |
| Tổn hao | (5 − 3,6) × I = 0,7 W tại 0,5 A, 1,4 W tại 1 A | Thấp hơn nhiều |
| Thời gian sạc 10 Ah | khoảng 20 giờ | khoảng 7–10 giờ |

Cảnh báo: **không dùng module sạc kiểu TP4056 cho LFP**, vì chúng sạc tới 4,2 V và làm quá áp cell LFP.

Điện áp sạc cuối của bộ sạc phải thấp hơn ngưỡng cắt quá áp của BMS (thường khoảng 3,65 V `[CHƯA XÁC MINH]`).

### 6.3 Cắt sạc theo nhiệt độ

NTC gắn ở **pack** (sát cell), không đặt trên board, vì board nóng hơn cell. Điểm cắt thực hiện bằng phần cứng, không qua firmware.

Với NTC 10 kΩ B3950 và điện trở kéo 7,15 kΩ (giá trị CAM4G), ngưỡng dưới của chip nằm trong dải 42,5–47,5 % VIN, nên điểm cắt thực tế rơi vào khoảng **35–40 °C**, không phải đúng 40 °C `[ƯỚC TÍNH]`. Phía lạnh, ở 0 °C điện áp TEMP sát ngưỡng trên, tức điểm cắt lạnh cũng sát. Đo điểm cắt thực bằng tủ sấy (M-05) và chỉnh lại theo NTC của pack thật.

### 6.4 Sạc và tải dùng chung pin

Ở prototype, tải đấu thẳng vào VBAT cùng bộ sạc. Khi camera chạy, dòng từ pin thường lớn hơn dòng sạc 0,5 A, nên pin không đầy và bộ sạc có thể không bao giờ báo xong. Chấp nhận trong prototype dưới dạng "chỉ sạc khi thiết bị nghỉ" và ghi rõ trong tài liệu thử nghiệm. Production dùng power-path để tách tải khỏi pin (O-05).

## 7. Yêu cầu với pack và BMS

| Mục | Yêu cầu |
|---|---|
| Hóa học | LFP 1S, 3,2 V danh định |
| Dung lượng | 10 Ah (prototype), tới 15 Ah (thiết kế) |
| Dòng xả liên tục của BMS | ≥ 8–10 A, đủ cho đỉnh 5,6 A cộng dư |
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

VBUS, VBAT trước và sau header đo dòng, +5V_BOOST, +5V_SOC, +5V_MODEM, +3V3, GND (nhiều điểm), SW của boost, CHRG, DONE, TEMP, MCU_IRQ, SDA, SCL.

## 10. Việc còn mở

- Chọn pack và BMS cụ thể (O-03).
- Chọn chip sạc production và power-path (O-05).
- Đo dòng nghỉ của boost và của modem breakout ở chế độ Watch (R-04).
- ADC đo pin: điện áp LFP có thể tới 3,65 V, cao hơn rail 3,3 V, nên mạch chia áp là bắt buộc.
