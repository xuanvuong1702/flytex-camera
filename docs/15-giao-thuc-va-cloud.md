# 15 — Giao thức và cloud

- Trạng thái: Bản chốt v1.1 (đi kèm `spec/` và mã trong repo)
- Ngày: 2026-11-09
- Thay thế: mục 5 của [03](03-giao-dien.md) (regmap) và mục 2–4 của [05](05-ket-noi-va-cloud.md) (kênh đánh thức, cloud). Các mục đó giữ làm lịch sử quyết định.

Số liệu nguồn nằm trong `spec/`: [registers.toml](../spec/registers.toml), [mqtt.toml](../spec/mqtt.toml), [b2b.toml](../spec/b2b.toml). Tài liệu này giải thích **vì sao** và **dùng thế nào**; khi hai bên khác nhau, spec thắng.

## 1. Phiên bản và tương thích

| Hạng mục | Quy tắc |
|---|---|
| Phiên bản giao thức | `PROTO_VER` = [7:4] chính, [3:0] phụ. Hiện tại **1.1** |
| Khác major | SoC **phải** từ chối làm việc, báo lỗi rõ, không đoán |
| Khác minor | Được phép: bên minor cao hơn có thể có thêm thanh ghi; bên thấp hơn bỏ qua thanh ghi lạ |
| Đổi nghĩa thanh ghi cũ | Không được. Phải tăng major |
| File sinh | Sửa `spec/*.toml` rồi chạy `python spec/generate.py`; CI chặn file sinh lệch spec |

Phiên bản 1.1 thêm `SYS_FLAGS`, `WAKE_CHAN`, `WAKE_PERIOD_S`, `UPTIME_S`, `BOOT_COUNT` và đổi `WAKE_IN_S` sang big-endian. Không có thiết bị nào đang chạy 1.0 nên không cần tương thích ngược.

## 2. Giao thức I2C

### 2.1 Điện và bus

| Thông số | Giá trị | Ghi chú |
|---|---|---|
| Địa chỉ 7 bit | `0x30` | |
| Tốc độ mặc định | 100 kHz | Nâng lên 400 kHz sau khi đo M-16 |
| Pull-up | 2,2 kΩ tới +3V3, đặt trên PWR | Một phía, không lặp |
| Điện dung bus | ≤ 400 pF | Cáp B2B ≤ 60 mm |
| Mức logic | 3,3 V cả hai phía | Modem 1,8 V do breakout lo |

### 2.2 Khung truyền

```
START | 0x30<<1|W | reg | data... | STOP              (ghi)
START | 0x30<<1|W | reg | Sr | 0x30<<1|R | data... | NACK | STOP   (đọc)
```

- Thanh ghi tự tăng sau mỗi byte.
- Đọc quá byte cuối của vùng thanh ghi (0x17): NACK, không quấn vòng.
- Ghi vào vùng chỉ đọc, ghi địa chỉ không định nghĩa: NACK.
- Không dùng clock stretching; MCU phải trả lời trong thời gian phần cứng cho phép. Nếu vi điều khiển không kịp, hỏng bus là lỗi thiết kế, không phải lỗi SoC.

### 2.3 Nhóm nhiều byte

Ví dụ `VBAT_MV` (0x06–0x07) và `WAKE_IN_S` (0x0C–0x0F):

```
SoC đọc:   0x06  →  chốt toàn bộ giá trị, trả byte cao
           0x07  →  trả byte thấp của giá trị đã chốt
SoC ghi:   0x0C..0x0F  →  byte 0x0F commit; trước đó giá trị cũ vẫn dùng
```

Nhờ vậy không bao giờ đọc được nửa giá trị cũ nửa giá trị mới.

### 2.4 Sự kiện và IRQ

1. MCU đặt bit trong `EVENT` khi có sự kiện.
2. Nếu bit đó được bật trong `EVENT_MASK`, MCU kéo `MCU_IRQ` xuống mức thấp.
3. SoC đọc `EVENT`, nhận các bit đã đặt; thanh ghi bị xóa.
4. Còn bit nào chưa đọc hay không? Nếu không, MCU thả `MCU_IRQ`.
5. Sự kiện đến trong lúc đang đọc sẽ đặt lại bit và giữ `MCU_IRQ` thấp.

SoC **không** polling theo chu kỳ khi đã ngủ; chỉ đọc khi IRQ xuống hoặc khi thức theo lịch.

`EVENT_MASK` reset là `0x3F`, nên `WAKE_ALARM` (bit 6) **không** kéo `MCU_IRQ` theo mặc định. Ứng dụng đọc `EVENT` ngay sau khi khởi động nên vẫn nhận được sự kiện đánh thức; nếu muốn có IRQ cho kênh đánh thức, ghi `EVENT_MASK = 0x7F` khi khởi động. Đừng giả định bit 6 có trong mask.

### 2.5 Bắt tay tắt máy

| Bước | Ai | Việc | Thời gian |
|---|---|---|---|
| 1 | MCU | Đặt `EVENT.SHUTDOWN_REQ`, kéo IRQ | — |
| 2 | SoC | Đóng file, `fsync`, đóng container, ghi `CMD = SOC_SHUTDOWN_DONE` | ≤ 10 s |
| 3 | MCU | Chờ 500 ms cho các rail xả, cắt `+5V_SOC` | 500 ms |
| 4 | MCU | Nếu quá 10,5 s (10 s chờ + 500 ms) không có `SOC_SHUTDOWN_DONE`: cắt cưỡng bức, `FAULT_CODE = SOC_NO_HANDSHAKE` | 10,5 s |

Thời gian 10 s, 500 ms và 20 s (chờ `SOC_READY`) là hằng số cấu hình trong `firmware/mcu/include/flytex/config.h`; phải đo lại ở M-13 và chỉnh. Mất điện đột ngột vẫn có thể xảy ra (BMS cắt, pin rơi); thiết kế file phải chịu được, xem [14](14-kien-truc-phan-mem.md) §4.3.

### 2.6 Lỗi bus và phục hồi

- SoC có timeout cho mọi giao dịch; quá hạn thì bỏ, không treo tiến trình.
- Nếu bus kẹt (SDA thấp) quá 1 s, SoC khởi tạo lại bộ điều khiển I2C; nếu vẫn kẹt, khởi động lại thiết bị.
- MCU không tự reset SoC vì lỗi bus; nó chỉ báo `FAULT_CODE = I2C_BUS` và để SoC quyết định.

## 3. Định danh thanh ghi và mã

Xem bảng sinh: [spec/generated/regmap.md](../spec/generated/regmap.md). Không chép lại danh sách ở đây.

## 4. Nhận lệnh khi ngủ (kênh đánh thức)

### 4.1 Vấn đề

"Watch" trong bản nháp là "eDRX + MQTT" trong khi SoC tắt. MQTT có TLS cần một máy chạy TCP; MCU STM32L0 không làm được việc đó trong ngân sách 10 µA. Bản nháp không nói ai giữ phiên. Đây là lỗ hổng kiến trúc, không phải chi tiết hiện thực. Xem [13](13-tinh-kha-thi.md) F-02.

### 4.2 Thiết kế chốt: modem giữ mạng, RI đánh thức MCU

```
Cloud ──► SMS "W <token>" ──► Modem (eDRX) ──► RI ──► MCU ──► bật +5V_SOC
                                                                    │
                                                          SoC đọc SMS, xác thực token
                                                                    │
                                                          SoC kết nối MQTT, nhận lệnh
```

| Thành phần | Việc | Ghi chú |
|---|---|---|
| Modem | Ở eDRX, vẫn đăng ký mạng, nhận SMS | PSM sẽ làm SMS đến trễ hàng giờ; xem §4.4 |
| `MODEM_RI` (B2B chân 21) | Modem kéo RI khi có SMS; MCU đọc như một nguồn đánh thức | Đã thêm vào `spec/b2b.toml` |
| MCU | Thức, xác thực tiền tố, bật rail SoC, đặt `EVENT.WAKE_ALARM` | Không tự đọc nội dung SMS |
| SoC | Đọc SMS qua AT, xác thực token, kết nối MQTT | Token dùng một lần, có hạn |

Đây là kênh **SMS** (`WAKE_CHAN = 2`). Ưu điểm: không cần thêm UART từ modem tới MCU, không cần MCU chạy TCP. Nhược điểm: mỗi lần đánh thức tốn một SMS của nhà mạng, và độ trễ phụ thuộc paging của eDRX (thường 5–30 s).

### 4.3 Các kênh khác

| `WAKE_CHAN` | Cơ chế | Trạng thái |
|---|---|---|
| 0 `OFF` | Không đánh thức từ xa; chỉ PIR và lịch | Dùng cho Eco |
| 1 `MODEM_TCP_POLL` | MCU đánh thức modem theo chu kỳ, hỏi một endpoint TCP | **Chưa khả thi**: MCU không có UART tới modem trong thiết kế hiện tại; cần UART phụ (O-12) |
| 2 `SMS` | Như §4.2 | Khuyến nghị cho Watch |
| 3 `EDRX_MQTT` | SoC bật, giữ MQTT | Chỉ khi cần độ trễ <2 s và chấp nhận 4 ngày pin |

Nếu muốn kênh 1, phải thêm một UART từ modem tới MCU (EC200U có UART phụ hay không: `[CHƯA XÁC MINH]`), hoặc dùng modem có bộ lệnh MQTT trong firmware. Ghi thành O-12, không giả định.

### 4.4 eDRX và PSM: hai thứ khác nhau

| Chế độ | Thiết bị có nhận được downlink không? | Dòng trung bình `[ƯỚC TÍNH]` | Dùng cho |
|---|---|---|---|
| DRX thường | Có, liên tục | 130–300 mW | Không dùng (quá tốn) |
| eDRX | Có, theo chu kỳ paging (5–40 s) | 10–25 mW | Watch |
| PSM | Không, chỉ khi thức theo TAU | 1–5 mW | Eco |
| Tắt modem | Không | 0 | Eco tiết kiệm nhất |

Bản nháp gộp eDRX/PSM làm một "chế độ tiết kiệm"; thực tế chúng phục vụ hai chế độ khác nhau của sản phẩm. Thời gian eDRX/PSM do mạng cấp, không phải thiết bị muốn là được (R-07).

### 4.5 Ngân sách chờ `[ƯỚC TÍNH]`

Pack 27,2 Wh dùng được (10 Ah LFP):

| Chế độ | Dòng trung bình | Thời gian chờ |
|---|---|---|
| Eco, modem tắt, 1 mA | 3,7 mW | ~300 ngày |
| Watch, eDRX 3 mA | 11 mW | ~100 ngày |
| Watch, eDRX 5 mA | 18,5 mW | ~60 ngày |
| EDRX_MQTT, SoC bật 40 mA | 148 mW | ~7 ngày |

Cộng thêm tự tiêu của BMS (giả định 100 µA) và tự xả LFP (~2 %/tháng). Các số này phải thay bằng M-02, M-03, M-10.

## 5. MQTT

### 5.1 Phong bì và chủ đề

Xem bảng sinh [spec/generated/mqtt.md](../spec/generated/mqtt.md) và JSON schema [spec/generated/mqtt.schema.json](../spec/generated/mqtt.schema.json).

| Nguyên tắc | Chi tiết |
|---|---|
| `id` duy nhất | 16 hex, do nguồn gửi sinh; cloud dùng để chống trùng |
| `ts` | Unix giây UTC; cloud không tin tuyệt đối, dùng để sắp xếp |
| QoS 1 | Có thể trùng, không được mất; xử lý trùng bằng `id` |
| `status` retained | App mở là thấy trạng thái ngay, không cần chờ |
| Kích thước | Sự kiện ≤ 512 B; clip đi đường HTTPS, không đi MQTT |
| Thứ tự | Không đảm bảo; sắp xếp theo `ts`, không theo thứ tự đến |

### 5.2 Lệnh và xác nhận

Bản tin lệnh dùng **dạng phẳng**: `type` là tên lệnh, tham số nằm ở mức ngoài cùng. Không có trường `cmd`/`args`; bản tin lồng nhau bị từ chối `BAD_ARGS`. Đây là hợp đồng hiện hành, sinh từ `spec/mqtt.toml` (khối `[command_wire]`).

```json
{"v":1,"id":"0123456789abcdef","dev":"abc123def456","ts":1700000000,
 "type":"mode.set","mode":"watch"}
```

1. Cloud gửi lệnh với `id`, `type` = tên lệnh, tham số cùng cấp.
2. Thiết bị kiểm tra: phiên bản, tên lệnh, tham số bắt buộc, enum, dải giá trị.
3. Thiết bị chạy handler; trả `ack` cùng `id`, `ok`, `result` hoặc `error`.
4. Cloud timeout sau 15 s; gửi lại tối đa 3 lần với cùng `id`; thiết bị phải idempotent theo `id` (nhớ 16 `id` gần nhất trong NVM).
5. Lệnh không hiện thực trả `NOT_IMPLEMENTED`, không im lặng.

`mode.set` khi đang ghi trả `BUSY`; đây là hành vi đúng, không phải lỗi.

### 5.3 Đồng bộ giờ

- Thiết bị có RTC (DS3231 hoặc RTC trong SoC), trôi vài giây/ngày.
- Nguồn chính: NTP khi có mạng; nguồn phụ: `time.sync` từ cloud.
- Sau khi đồng bộ, ghi độ lệch vào log; nếu lệch > 5 phút, ghi `FAULT` nhẹ và đồng bộ lại.
- Lịch hoạt động theo giờ địa phương trong `config.timezone`; đổi giờ phải tính lại `WAKE_IN_S`.

## 6. Xem trực tiếp

### 6.1 Kiến trúc

```
Camera ──MIPI──► RV1106 (ISP + H.264) ──RTSP/SRT──► MediaMTX ──WHEP──► Web/app
                                                      │
Cloud ──cmd live.start──► thiết bị ──ack {live_url, expires_s}──► Cloud
```

- Thiết bị **đẩy** luồng ra relay (không cần mở cổng vào, qua được CGNAT).
- Relay mã nguồn mở MediaMTX, có WHIP/WHEP (WebRTC).
- `live_url` là URL WHEP kèm token ngắn hạn; hết `expires_s` thì token hết hiệu lực.
- Xác thực: token ký theo thiết bị và phiên; relay kiểm tra, không tin thiết bị.

### 6.2 Ngân sách trễ

| Thành phần | Giá trị `[ƯỚC TÍNH]` |
|---|---|
| Mã hóa 720p30 | 50–100 ms |
| Đóng gói + đẩy RTSP/SRT | 20–60 ms |
| Mạng 4G | 40–100 ms |
| Relay | 20–50 ms |
| Đệm jitter + giải mã | 80–250 ms |
| **Tổng** | **0,2–0,6 s** |

Mục tiêu ≤1,5 s có dư nếu dùng WebRTC. HLS không đạt (2–6 s), xem [13](13-tinh-kha-thi.md) F-06.

### 6.3 Bitrate thích ứng

| Sóng | Độ phân giải | Bitrate | Ghi chú |
|---|---|---|---|
| Tốt (RSRP > −90 dBm) | 720p25 | 1,2–1,8 Mbps | |
| Trung bình | 720p15 | 0,8 Mbps | |
| Yếu | 480p15 | 0,4 Mbps | Vẫn đạt 1,5 s |
| Rất yếu | 360p10 | 0,2 Mbps | Chỉ để xem, không ghi |

Thiết bị đo `rssi`/`rsrp` mỗi 30 s khi đang live và hạ cấp khi cần. Đo thật ở M-30, M-31.

## 7. Cấp phát định danh và chứng chỉ

| Bước | Việc | Ai làm |
|---|---|---|
| 1 | Sinh `device_id` 12 ký tự, ghi vào phân vùng định danh | Nhà máy |
| 2 | Sinh cặp khóa, CSR, ký bởi CA của dự án | Nhà máy hoặc cloud |
| 3 | Nạp chứng chỉ, khóa riêng, CA vào `/data/identity/` | Nhà máy |
| 4 | Ghi số serial, ngày, phiên bản firmware vào cơ sở dữ liệu sản xuất | Nhà máy |
| 5 | Kiểm cuối dây: kết nối MQTT bằng chứng chỉ riêng, từ chối khi sai | Nhà máy |

- Khóa riêng không rời thiết bị, không nằm trong image firmware.
- Có thể thu hồi theo `device_id` ở cloud; thiết bị bị thu hồi phải bị từ chối ở broker.
- Không có mật khẩu mặc định dùng chung cho cả lô.

## 8. OTA

**Chưa hiện thực.** Hợp đồng dưới đây là mục tiêu, không phải mô tả mã hiện có.

| Hạng mục | Mục tiêu |
|---|---|
| Phân vùng | A/B cho rootfs, có quay lui |
| Kích thước | Image ≤ 60 % dung lượng một slot (eMMC 8 GB: thoải mái) |
| Chữ ký | Ký bằng khóa offline; thiết bị chỉ nhận image đúng chữ ký và đúng `device_id`/model |
| Tải | HTTPS, có resume; dung lượng lớn nên không qua MQTT |
| Kích hoạt | Ghi slot còn trống, đặt cờ, khởi động lại, kiểm tra sức khỏe, nếu hỏng quay lui |
| Thời điểm | Chỉ khi đang sạc và pin >50 %, không cắt ngang clip |
| Lệnh | `ota.start` trả `NOT_IMPLEMENTED` cho đến khi có hiện thực |

Trên biến thể 256 MB SPI NAND, A/B không vừa; đây là lý do [13](13-tinh-kha-thi.md) F-08 chốt biến thể eMMC.

## 9. Chẩn đoán và log

| Dữ liệu | Lưu ở | Gửi lên khi nào |
|---|---|---|
| Log vòng | `/data/diag/log.txt` | Theo yêu cầu, hoặc khi có fault |
| Lý do khởi động | `/data/diag/boot.json` | Trong bản tin `boot` |
| Số lần khởi động | `BOOT_COUNT` + file | Trong `boot`, `status` |
| Điện áp lúc tắt | `/data/diag/last_shutdown.json` | Trong `shutdown` nếu còn mạng |
| Số lần mất điện đột ngột | `/data/diag/powerloss.count` | Trong `status` |

Log không chứa khóa, token, nội dung SMS, ảnh.

## 10. Bảo mật tối thiểu

1. TLS 1.2+ cho MQTT và HTTPS; không có ngoại lệ cho "mạng nội bộ".
2. Chứng chỉ riêng từng thiết bị; CA riêng của dự án; có danh sách thu hồi.
3. Token WHEP ngắn hạn, ký, gắn với phiên.
4. SMS đánh thức phải có token dùng một lần; SMS không có token bị bỏ qua và ghi log.
5. Console UART chỉ truy cập được khi mở vỏ; không bật shell qua mạng.
6. OTA có chữ ký (khi làm).
7. Rà soát: mọi bí mật nằm ở phân vùng định danh, không trong image, không trong log.
