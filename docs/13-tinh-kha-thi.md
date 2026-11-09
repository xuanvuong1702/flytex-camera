# 13 — Phân tích khả thi

- Trạng thái: Phân tích v1.0, có kiểm chứng nguồn ngoài
- Ngày: 2026-11-09
- Đầu vào: bản dự thảo v0.1 ([00](00-yeu-cau.md)…[12](12-bai-hoc-tu-cam4g.md)), datasheet/tài liệu nhà cung cấp, mã trong repo này.
- Quy ước nhãn: giữ nguyên như [README](../README.md). Thêm `[ĐÃ XÁC MINH]` cho những gì đã đối chiếu tài liệu nguồn trong lần phân tích này.

## 1. Kết luận

**Khả thi về kỹ thuật, chưa khả thi về tiến độ nếu giữ nguyên bản nháp v0.1.** Kiến trúc ba board và cách chọn module là đúng hướng. Nhưng bản nháp có **bốn lỗi thiết kế sẽ chặn board** nếu vẽ trước khi sửa, và **ba con số năng lượng không đủ dư** để đạt yêu cầu 7 giờ ban đêm.

| Câu hỏi | Trả lời ngắn |
|---|---|
| Có làm được camera 4G chạy pin 7 giờ không? | Có, nhưng **không** với pack 10 Ah cho kịch bản đêm có IR + live. Cần 15 Ah hoặc giảm công suất IR. |
| Kiến trúc PWR/CMP/MDM có đúng không? | Đúng. Giữ. |
| Có thể bắt đầu vẽ board ngay? | **Không.** Phải qua G0 và sửa F-01…F-04. |
| Rủi ro lớn nhất là gì? | Không phải mạch điện, mà là **nhiệt trong vỏ kín** và **thời gian chờ SDK/vỏ/chứng nhận**. |
| Bao lâu tới lô thí điểm? | `[ƯỚC TÍNH]` 9–12 tháng cho một kỹ sư toàn thời gian, 6–8 tháng cho hai người, chưa tính chứng nhận. |
| Chi phí prototype? | `[ƯỚC TÍNH]` 1.500–3.500 USD cho giai đoạn 0–4, chưa tính công và dụng cụ đo. |

## 2. Phương pháp

1. Đối chiếu từng con số trong [02](02-thiet-ke-nguon.md) §3 và [09](09-san-xuat.md) §8, tính lại từ đầu.
2. Đối chiếu các giả định A-01…A-05 với tài liệu nhà cung cấp.
3. Đọc lại hợp đồng giao diện [03](03-giao-dien.md) và tìm chỗ không hiện thực được bằng phần cứng/firmware đã mô tả.
4. Với mỗi lỗi tìm được: nêu bằng chứng, hệ quả, cách sửa, và nơi sửa.
5. Viết mã và test cho những phần kiểm chứng được bằng phần mềm (xem §8).

## 3. Những gì đã xác minh trong lần này

| Nội dung | Kết quả | Nguồn |
|---|---|---|
| Core1106 là module RV1106 | Đúng. Core1106D dùng RV1106, Cortex-A7 1,2 GHz, NPU 1 TOPS, 30×30 mm, 112 chân | [Luckfox Core1106D](https://wiki.luckfox.com/Core1106D/Introduction/) `[ĐÃ XÁC MINH]` |
| Số cổng USB của Core1106 | **Đúng 1 cổng USB 2.0 Host/Device** | [Luckfox Core1106D](https://wiki.luckfox.com/Core1106D/Introduction/) `[ĐÃ XÁC MINH]` |
| Bộ mã hóa | Có mã hóa cứng MJPEG/H.264/H.265, ISP tới 8 MP | cùng nguồn `[ĐÃ XÁC MINH]` |
| MIPI CSI | 2 cổng 2 lane, hoặc 1 cổng 4 lane | cùng nguồn `[ĐÃ XÁC MINH]` |
| UART/I2C/GPIO | 6 UART (tới 4 Mbps), 5 I2C, 12 PWM, 2 SDIO | cùng nguồn `[ĐÃ XÁC MINH]` |
| Bản module cho OTA A/B | Có bản 256 MB SPI NAND và bản 8 GB eMMC | cùng nguồn `[ĐÃ XÁC MINH]` |
| Modem EC200U | Có USB 2.0 HS, driver RNDIS/ECM cho Linux (theo tài liệu Quectel đã dẫn trong [05](05-ket-noi-va-cloud.md) §1.1) | tài liệu Quectel `[KẾ THỪA]` |
| Sạc LFP 1S có power-path | Có IC chuyên cho LFP 1 cell, ví dụ LTC4098-3.6 | [Analog Devices LTC4098-3.6](https://www.analog.com/en/products/ltc4098-3.6.html) `[CHƯA XÁC MINH]` tình trạng còn hàng |

Điểm quan trọng nhất: **Core1106 chỉ có một cổng USB**, đóng O-01 và làm thay đổi D-13.

## 4. Lỗi thiết kế phải sửa trước khi vẽ board

### F-01 `[CHẶN]` Một cổng USB cho hai việc: modem và nạp firmware

**Bằng chứng.** Core1106D có đúng 1 cổng USB 2.0 Host/Device. Bản nháp dùng cổng này cho modem ([05](05-ket-noi-va-cloud.md) §1.1) và nói "nạp SoC qua thẻ SD hoặc pad USB riêng" ([03](03-giao-dien.md) §4) mà không có cơ chế chuyển.

**Hệ quả.** Nếu firmware hỏng và mạng không lên, thiết bị coi như "brick" tại hiện trường, vì đường nạp duy nhất (USB) đang nối vào modem. Trong giai đoạn phát triển, mỗi lần nạp phải tháo modem.

**Cách sửa (chọn một, chốt ở G0).**
- **A. Mux USB** (khuyến nghị): thêm một mux USB 2.0 hai kênh giữa SoC và {modem, pad dịch vụ}, điều khiển bằng GPIO. Chi phí ~0,3 USD, thêm 4 chân B2B dự phòng đã có. Cho phép nạp tại hiện trường.
- **B. Chỉ nạp qua thẻ SD**: rẻ nhất, nhưng thẻ phải tiếp cận được khi mở vỏ và bootloader phải hỗ trợ. Rủi ro nếu vỏ kín.
- **C. Cổng USB-C hai chế độ**: phức tạp, không nên.

**Sửa ở đâu:** [03](03-giao-dien.md) §4, O-01 → đóng, D-13 giữ nguyên, thêm D-19.

### F-02 `[CHẶN]` "Watch = eDRX + MQTT" không hiện thực được khi SoC tắt

**Bằng chứng.** [01](01-kien-truc.md) §3 định nghĩa S1 Watch: SoC **tắt**, modem bật tiết kiệm. [05](05-ket-noi-va-cloud.md) §2 chọn "eDRX + MQTT". MQTT là giao thức lớp ứng dụng có TLS; nó cần một máy chạy được TCP/TLS, tức SoC. MCU STM32L0 với ngân sách 10 µA và 64 KB flash không chạy được TLS + MQTT. Vậy ai giữ phiên MQTT khi SoC tắt? Bản nháp không nói.

Nếu giữ SoC bật để giữ MQTT: SoC Linux nghỉ ở mức 30–80 mA `[ƯỚC TÍNH]`, pack 27,2 Wh chỉ được 14–38 ngày, và tiêu chí NFR-04 (<1 mA) sai gấp 30–80 lần.

**Hệ quả.** Nếu không sửa, chế độ Watch hoặc không chạy được, hoặc chạy được nhưng phá mục tiêu pin.

**Cách sửa.** Tách "kênh đánh thức" khỏi MQTT. Chốt ba kênh, chọn bằng thanh ghi `WAKE_CHAN` (đã thêm vào spec v1.1):

| Kênh | Cơ chế | Độ trễ lệnh | Dòng trung bình `[ƯỚC TÍNH]` |
|---|---|---|---|
| `MODEM_TCP_POLL` | MCU đánh thức modem theo chu kỳ, modem mở TCP ngắn tới cloud, hỏi có lệnh không | 1–3 chu kỳ, mặc định 15 phút | ~15–25 mW (gồm cả chân ngủ) |
| `SMS` | Cloud gửi SMS, modem báo `+CMTI`, MCU đánh thức SoC | 5–30 s | ~10–20 mW |
| `EDRX_MQTT` | SoC bật, giữ MQTT | 1–2 s | 130–300 mW |

Với pack 27,2 Wh: `MODEM_TCP_POLL` cho ~40 ngày chờ, `SMS` ~45 ngày, `EDRX_MQTT` ~4 ngày. Chế độ Eco (modem tắt) ~300 ngày. Đây là lý do Watch và Eco phải là hai chế độ khác nhau, không phải một tham số của cùng một cơ chế.

**Điểm còn hở:** MCU không tự chạy được TCP; nó chỉ cấp nguồn modem và báo `WAKE_ALARM`, còn phần TCP do modem thực hiện qua lệnh AT, phần xử lý lệnh do SoC sau khi thức. Nếu muốn MCU tự quyết định "có lệnh hay không" mà không bật SoC, phải thêm một MCU có TCP stack hoặc dùng modem có MQTT AT command — chưa xác minh EC200U có bộ lệnh MQTT. Ghi thành O-12.

**Sửa ở đâu:** [05](05-ket-noi-va-cloud.md) §2, [01](01-kien-truc.md) §3, spec `WAKE_CHAN`/`WAKE_PERIOD_S`, [15](15-giao-thuc-va-cloud.md) §4.

### F-03 `[CHẶN NHẸ]` Ngân sách rail 5 V thiếu khi modem phát

**Bằng chứng.** Boost 3 A ([02](02-thiet-ke-nguon.md) §4). Tải: SoC + camera + thẻ SD đỉnh ~1,5 A `[ƯỚC TÍNH]`; modem Cat-1 khi phát burst lấy từ VBAT có thể tới ~2 A trong vài trăm µs `[CHƯA XÁC MINH — cần datasheet EC200U]`, quy về 5 V sau hạ áp ~0,9 hiệu suất là ~1,7 A. Tổng 3,2 A > 3 A.

Tụ bulk 470 µF trên breakout giúp san burst, nhưng công tắc tải và connector vẫn phải chịu đỉnh, và nếu boost chạm giới hạn dòng thì điện áp 5 V tụt, có thể reset SoC giữa lúc ghi.

**Cách sửa.**
1. Đo đỉnh dòng modem ở G0 bằng shunt + oscilloscope, không đoán.
2. Nâng rail modem lên 3 chân B2B (đã sửa trong `spec/b2b.toml`) và chọn công tắc tải ≥ 2 A.
3. Cân nhắc boost thứ hai hoặc buck-boost riêng cho modem, lấy trực tiếp từ VBAT — cũng là phương án dự phòng cho dòng nghỉ của boost ở chế độ Watch (O-04).
4. Đặt tụ bulk 470 µF **sát chân modem**, không chỉ trên board PWR.

**Sửa ở đâu:** [02](02-thiet-ke-nguon.md) §2, [03](03-giao-dien.md) §1 và §3, `spec/b2b.toml`.

### F-04 `[CHẶN]` Sạc tuyến tính 0,5 A biến thiết bị thành "luôn cạn pin"

**Bằng chứng.** [02](02-thiet-ke-nguon.md) §6.2: sạc 0,5 A, 10 Ah → 20 giờ; 15 Ah → 30 giờ. Kèm §6.4: tải đấu thẳng VBAT, dòng tải thường lớn hơn dòng sạc.

**Hệ quả.** Người dùng cắm sạc qua đêm 12 giờ được 6 Ah, trong khi một ngày dùng có thể tiêu 5–10 Wh. Pin không bao giờ đầy; tuổi thọ thực tế giảm một nửa; và tổn hao (5−3,6)×1 A = 1,4 W nằm trong vỏ kín ở 45 °C là bài toán nhiệt, không chỉ là hiệu suất.

**Cách sửa.** Đưa bộ sạc xung có power-path vào **prototype**, không đợi production:
- IC chuyên LFP 1S có power-path (ví dụ LTC4098-3.6, hoặc IC buck-boost chọn được điện áp sạc 3,6 V); dòng sạc 1,5–2 A;
- hoặc chấp nhận chậm nhưng **phải** có power-path để tải không lấy từ pin khi đang sạc.

Điều kiện đi kèm: pack/BMS phải cho sạc ≥1,5 A; nguồn USB-C phải cấp được ≥1,5 A (với CC chỉ Rd, nhiều củ sạc vẫn cấp 5 V/2 A, nhưng không đảm bảo — cần đo).

**Sửa ở đâu:** [02](02-thiet-ke-nguon.md) §6.2, D-16 đổi thành "sạc xung có power-path ngay từ Rev A".

### F-05 `[QUAN TRỌNG]` 7 giờ ban đêm gần như không dư

Tính lại từ [02](02-thiet-ke-nguon.md) §3 (10 Ah LFP = 32 Wh danh định, 85 % dùng được = 27,2 Wh):

| Kịch bản | Công suất | 7 giờ | % pack dùng được | Thời gian chạy tối đa |
|---|---|---|---|---|
| Ghi cục bộ | 1,4 W | 9,8 Wh | 36 % | 19,4 h |
| Ghi + live | 2,3 W | 16,1 Wh | 59 % | 11,8 h |
| Đêm IR + live | 3,8 W | 26,6 Wh | **98 %** | **7,2 h** |
| Đêm, pack 15 Ah | 3,8 W | 26,6 Wh | 65 % | 10,7 h |

Ba vấn đề nằm sau con số 98 %:
1. Mọi công suất đều là `[KẾ THỪA]` `[ƯỚC TÍNH]`, chưa đo.
2. LFP mất 15–20 % dung lượng ở 0 °C; đêm lạnh làm con số 7,2 h tụt xuống dưới 6 h.
3. Dòng tự tiêu của BMS (50–500 µA `[ƯỚC TÍNH]`) không nằm trong phép đo của board nhưng vẫn tiêu pin.

**Cách sửa.** Chọn pack 15 Ah ngay từ prototype (board đã thiết kế cho 15 Ah), hoặc giảm công suất IR (PWM, chỉ bật IR khi ghi chứ không khi live), hoặc cả hai. Ghi yêu cầu **BMS tự tiêu ≤100 µA** vào tiêu chí mua pack.

### F-06 `[QUAN TRỌNG]` Chỉ số trễ live ≤1,5 s loại bỏ HLS

**Bằng chứng.** [05](05-ket-noi-va-cloud.md) §3 nêu relay mã nguồn mở (MediaMTX) và mục tiêu 1,5 s, nhưng không chốt giao thức phát.

**Phân tích ngân sách trễ** `[ƯỚC TÍNH]`:

| Thành phần | HLS | WebRTC (WHEP) |
|---|---|---|
| Mã hóa 720p | 50–100 ms | 50–100 ms |
| Đệm mạng/relay | 2–6 s (segment) | 100–300 ms |
| Truyền 4G | 40–100 ms | 40–100 ms |
| Giải mã + hiển thị | 50–150 ms | 30–80 ms |
| **Tổng** | **2,2–6,4 s** | **0,2–0,6 s** |

Vậy HLS không đạt; WebRTC đạt và còn dư. MediaMTX có WHIP/WHEP. Thiết bị đẩy luồng ra relay qua kết nối do thiết bị khởi tạo, nên CGNAT không chặn.

**Rủi ro còn lại:** Cat-1 tải lên 1–2 Mbps chỉ đạt khi sóng tốt. Cần bitrate thích ứng (720p → 480p) và đo ở ba nhà mạng (M-30). Nếu sóng yếu, mục tiêu 1,5 s vẫn giữ được nhưng độ phân giải phải giảm.

### F-07 `[QUAN TRỌNG]` Nhiệt trong vỏ nhôm kín là rủi ro tiến độ số một

Tính sơ bộ `[ƯỚC TÍNH]`: vỏ 120×80×45 mm, diện tích ngoài 0,037 m², hệ số tản tự nhiên + bức xạ ~8 W/m²·K → 0,30 W/K. Với 3,8 W, vỏ nóng hơn môi trường ~13 K. Ở 45 °C môi trường, vỏ ~58 °C, cạnh giới hạn 60 °C của module `[CHƯA XÁC MINH]`, chưa tính nắng chiếu trực tiếp (có thể cộng thêm 10–20 K) và chưa tính nhiệt cục bộ của SoC.

**Hệ quả.** Có thể phải giảm hiệu năng (720p15) hoặc thêm tản nhiệt khi trời nắng. Đây là lý do phải thử tủ sấy **trước** khi chốt vỏ.

**Bổ sung:** bề mặt 70 °C là nguy hiểm chạm (bỏng) — cần rà theo tiêu chuẩn an toàn và ghi nhãn; xem lại NFR-02.

### F-08 `[QUAN TRỌNG]` Chọn sai biến thể module: 256 MB SPI NAND không đủ cho OTA A/B + Python

Core1106D có bốn biến thể: 256 MB SPI NAND hoặc 8 GB eMMC; DDR 256/512 MB. Kế hoạch OTA A/B hai phân vùng rootfs cộng runtime Python (~20–40 MB) không vừa 256 MB NAND một cách thoải mái. `[ƯỚC TÍNH]`

**Cách sửa.** Chốt biến thể **eMMC** (Core1106D1408 hoặc D1808) cho thiết bị; dùng bản NAND chỉ cho dev board nếu đã mua. Cập nhật A-01.

### F-09 `[NHỎ]` Tài liệu tự mâu thuẫn

| # | Chỗ mâu thuẫn | Sửa |
|---|---|---|
| 1 | [03](03-giao-dien.md) §5 `WAKE_IN_S` ghi "little-endian" nhưng quy tắc 3 lại nói đọc byte cao chốt byte thấp | Chốt **big-endian** trong spec v1.1; đã sinh lại header/module |
| 2 | [03](03-giao-dien.md) §1 `+5V_MODEM` 0,5–0,6 A, trong khi [05](05-ket-noi-va-cloud.md) §1.2 yêu cầu breakout ≥0,6 A và modem Cat-1 có đỉnh lớn hơn | Nâng lên 1,8 A thiết kế, 3 chân B2B (F-03) |
| 3 | A-01 ghi "Core1106G3 N256"; tên module thực tế là Core1106D…N256, G3 là tên SoC bên trong | Sửa A-01 |
| 4 | [00](00-yeu-cau.md) NFR-02 dẫn định mức −20…+60 °C nhưng không rõ biến thể | Ghi `[CHƯA XÁC MINH]` và kiểm trong datasheet RV1106 |
| 5 | [08](08-kiem-chung.md) nhảy số M-25 → M-30 (thiếu M-26…M-29) | Giữ số cũ, ghi chú khoảng trống; không đánh số lại vì đã tham chiếu |
| 6 | [09](09-san-xuat.md) §8 chi phí 120 USD/bộ lấy từ CAM4G | Ghi rõ là tham khảo cũ, thay bằng bảng chi phí §7 dưới đây |

### F-10 `[NHỎ]` Chứng nhận: chưa có đường đi cụ thể

Thiết bị có modem LTE cần chứng nhận hợp quy thiết bị đầu cuối viễn thông và đánh giá EMC theo quy định Việt Nam; pin cần UN38.3 và IEC 62133. Số hiệu quy chuẩn hiện hành **chưa được xác minh trong tài liệu này** — phải hỏi đơn vị thử nghiệm trước khi thiết kế vỏ (O-10). Đừng để đến G5 mới hỏi.

## 5. Những gì khả thi và nên giữ

| Hạng mục | Đánh giá | Lý do |
|---|---|---|
| Tách PWR / CMP / MDM | **Giữ** | Mỗi board một luật layout; mỗi lần đặt chỉ sửa một board; đúng bài học CAM4G |
| MCU giám sát luôn bật | **Giữ** | SoC Linux không thể ở mức 1 mA; STOP + RTC của STM32L0 đạt ~1–2 µA `[ƯỚC TÍNH]` |
| Module OEM thay chip-down | **Giữ** | RV1106 cần DDR, nguồn nhiều rail, MIPI — tự làm là 6–12 tháng rủi ro |
| Không dùng INA226, dùng header đo dòng | **Giữ** | Đúng: 0,3 mA qua shunt 0,01 Ω chỉ 3 µV |
| NTC cắt sạc trên pack | **Giữ** | Đo đúng nhiệt độ cell; nhưng phải đo điểm cắt thật (M-05) |
| Relay mã nguồn mở | **Giữ**, chốt WebRTC/WHEP | HLS không đạt 1,5 s |
| I2C 100 kHz + IRQ | **Giữ** | 24 byte, không cần băng thông; IRQ tránh polling |
| 3,3 V logic giữa các board | **Giữ** | Đổi mức 1,8 V do breakout modem lo |
| Test trước khi vẽ board | **Giữ**, là điều kiện tiên quyết | Xem §9 |

## 6. Những gì bản nháp đánh giá thấp

| Rủi ro | Bản nháp | Đánh giá lại |
|---|---|---|
| R-03 pack thiếu cho đêm | TB/C | **C/C** — 98 % ở 10 Ah, cộng lạnh và BMS |
| R-04 dòng ngủ | TB/C | **C/C** — phụ thuộc BMS, boost, breakout; ba nguồn chưa đo |
| R-12 nhiệt SoC | TB/C | **C/C** — vỏ kín, nắng, không có mô phỏng |
| R-14 SDK thiếu OTA/encoder | TB/C | **TB/C** nhưng nay cụ thể hơn: encoder có, OTA A/B cần eMMC (F-08) |
| R-18 UART không đủ | C/TB | **Đã đóng** bằng D-07 (USB cho dữ liệu) — nhưng phụ thuộc F-01 |
| R-08 vỏ nhôm chắn sóng | C/C | **C/C** — phải quyết ăng-ten ngoài trước khi làm vỏ |
| R-07 eDRX/PSM | TB/C | **C/C** — và F-02 cho thấy kể cả có eDRX cũng chưa giải quyết được bài toán |
| Pin/BMS tự tiêu | không có | **Mới: C/TB** — thêm R-20 |
| Sạc 20 giờ | R-10 mức T | **Mới: C/TB** — F-04, thêm R-21 |
| Một cổng USB | R-06 mức TB/TB | **Nâng: C/C** — F-01, thêm R-22 |
| Nhiệt khi sạc | không có | **Mới: TB/TB** — R-23 |

## 7. Chi phí và tiến độ `[ƯỚC TÍNH]`

### 7.1 Linh kiện cho một bộ prototype

| Hạng mục | Giá tham khảo (USD) | Ghi chú |
|---|---|---|
| Core1106D14N256 hoặc D1408 | 12–25 | Chọn eMMC (F-08) |
| Dev board Luckfox Pico Max (cho G0) | 15–30 | Chỉ dùng để đo, không lên sản phẩm |
| Breakout EC200U-EU | 15–35 | Phải có USB ra, hạ áp, đổi mức |
| Module camera SC3336 có IR-CUT + IR LED | 8–18 | Pinout FPC 20 chân |
| Pack LFP 10 Ah có BMS | 25–45 | Cần UN38.3, NTC, BMS ≤100 µA |
| Pack LFP 15 Ah có BMS | 40–75 | Phương án khuyến nghị |
| PCB 4 lớp, 5 bộ | 60–120 | Tuỳ kích thước |
| PCBA (2 loại board, 5 bộ) | 250–600 | Stencil + lắp + linh kiện |
| Vỏ nhôm CNC hoặc hộp có sẵn | 20–80 | Prototype |
| Phụ kiện (ăng-ten, cáp, SIM) | 30–60 | Ba nhà mạng |
| **Tổng một bộ** | **~150–300** | Không gồm dev board và dụng cụ |

### 7.2 Dụng cụ đo (mua một lần)

| Dụng cụ | Giá (USD) | Dùng cho |
|---|---|---|
| Máy đo dòng áp (PPK2 hoặc tương đương) | 100–150 | M-01, M-02, M-09, M-10 |
| Đồng hồ vạn năng tốt | 50–100 | M-04…M-07 |
| Oscilloscope ≥100 MHz, 2 kênh | 300–800 (hoặc mượn) | M-08, M-19 |
| Nguồn bench có giới hạn dòng | 80–150 | Giai đoạn 0–2 |
| Tủ sấy 60–80 °C | mượn phòng lab | M-05, M-22 |

### 7.3 Tiến độ

| Giai đoạn | Thời gian (một kỹ sư) | Chồng lấn được |
|---|---|---|
| G0 đo trên dev board | 4–6 tuần | Firmware + cloud chạy song song |
| G1 board thử footprint | 3–4 tuần (gồm đặt và nhận) | |
| G2 PWR Rev A | 8–10 tuần | CMP thiết kế song song |
| G3 CMP Rev B | 8–10 tuần | Tích hợp bắt đầu |
| G4 tích hợp, vỏ | 6–8 tuần | |
| G5 chuẩn bị sản xuất | 8–12 tuần | Chứng nhận 8–16 tuần |
| **Tới lô thí điểm** | **9–12 tháng** | |
| **Tới bán được** | **14–18 tháng** | |

Hai kỹ sư (một phần cứng, một firmware) rút còn khoảng 6–8 tháng tới lô thí điểm.

## 8. Phần mềm: cái gì đã kiểm chứng được ngay

Phần cứng không thể kiểm chứng khi chưa mua linh kiện, nhưng phần mềm thì có. Repo này đã hiện thực và test được:

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Hợp đồng regmap sinh tự động | Xong | `spec/registers.toml` → header C + module Python + bảng |
| Pinout J_B2B sinh tự động, có kiểm dòng | Xong | `spec/b2b.toml` → bảng + kiểm hệ số dư |
| Hợp đồng MQTT sinh tự động | Xong | `spec/mqtt.toml` → JSON schema + module Python |
| Firmware MCU: regmap, nguồn, pin, nhiệt, lịch, NVM, STOP | Xong, test host | `firmware/mcu/tests` |
| Ứng dụng Linux: máy trạng thái, AT, ghi, hàng đợi, lệnh | Xong, test host | `app/tests` |
| Mô phỏng end-to-end firmware C + app | Xong | `sim/` |
| Công cụ đo G0 | Xong | `tools/measure` |
| Mã chạy camera thật (RK MPI) | **Chưa** | Cần SDK và dev board |
| Port STM32L0 thật | **Khung** | Cần SDK và board |
| OTA có chữ ký | **Chưa** | Cần chốt A/B ở G0 |

Điều này không thay thế phép đo phần cứng. Nó chỉ có nghĩa: khi có board, phần mềm không phải viết lại, và các hợp đồng đã có test.

## 9. Việc phải làm tiếp, theo thứ tự

### 9.1 Sửa tài liệu (làm ngay, không cần linh kiện)

1. Cập nhật [03](03-giao-dien.md) §1/§3/§4/§5 theo spec v1.1 (một cổng USB, rail modem, big-endian).
2. Cập nhật [02](02-thiet-ke-nguon.md): sạc xung power-path từ Rev A, BMS ≤100 µA, đỉnh modem.
3. Cập nhật [05](05-ket-noi-va-cloud.md) §2 theo kênh đánh thức; chốt WebRTC.
4. Cập nhật [00](00-yeu-cau.md): A-01 biến thể eMMC, NFR-02 nhiệt, NFR-04 phạm vi đo.
5. Ghi quyết định mới vào [11](11-nhat-ky-quyet-dinh.md), rủi ro mới vào [10](10-rui-ro.md).

### 9.2 Mua và đo (G0)

| Tuần | Việc | Kết quả |
|---|---|---|
| 1 | Đặt Core1106D1408, Pico Max, breakout EC200U, camera SC3336, pack 10/15 Ah, SIM ba mạng | Danh sách đặt hàng có MPN (xem §7) |
| 2 | Bring-up: boot, camera, ghi 720p, relay WebRTC | Ảnh, clip, số đo trễ |
| 3 | Đo dòng từng trạng thái bằng PPK2; đo đỉnh modem bằng shunt + scope | Bảng công suất thật thay §4 F-05 |
| 4 | eDRX/PSM ba mạng; nhiệt sơ bộ; quyết định pack | Đóng O-02, O-03, O-04, O-09, O-12 |

### 9.3 Điều kiện dừng (kill criteria)

Dừng hoặc đổi hướng nếu ở G0:
- công suất đêm có IR + live > 4,5 W (15 Ah cũng không đủ), hoặc
- nhiệt vỏ ở 45 °C môi trường > 65 °C khi đang ghi, hoặc
- tải lên 4G < 0,8 Mbps ở hai trong ba nhà mạng (live 720p không khả thi), hoặc
- SDK không mã hóa cứng được 720p30 ổn định (phải dùng phần mềm, tốn CPU và pin), hoặc
- không mua được pack LFP có BMS ≤100 µA và giấy tờ.

## 10. Tổng kết

Bản thiết kế đủ tốt để tiếp tục. Nó không đủ tốt để vẽ board ngay: bốn lỗi F-01…F-04 sẽ khiến board Rev A phải làm lại, và ba con số năng lượng (F-05) đang nằm sát giới hạn đến mức một phép đo xấu hơn 20 % là hỏng mục tiêu. Sửa tài liệu và đo ở G0 trước, rồi hãy đặt board — đúng như nguyên tắc "đo trước, chốt sau" mà chính repo này đặt ra.

Phần mềm trong repo đã sẵn sàng cho G0: hợp đồng có test, firmware có test, ứng dụng có test, mô phỏng chạy được. Khi có phần cứng, việc còn lại là thay transport giả bằng transport thật và đo.
