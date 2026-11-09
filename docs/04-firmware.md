# 04 — Firmware

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Phạm vi

Hai khối firmware: **MCU giám sát** (luôn bật, C, STM32L0) và **ứng dụng Linux** trên SoC (nhiều dịch vụ nhỏ). Giao thức giữa chúng ở [03](03-giao-dien.md) §5.

## 2. MCU giám sát

### 2.1 Nhiệm vụ

- Cấp và cắt nguồn cho SoC và modem; thực hiện bắt tay tắt máy an toàn.
- Nhận PIR, lịch, cắm/rút USB-C, trạng thái modem.
- Đo điện áp pin và nhiệt độ; báo lên SoC qua I2C.
- Giám sát pin cạn.
- Làm slave I2C, kéo `MCU_IRQ`.

### 2.2 Yêu cầu hiện thực

| Yêu cầu | Lý do |
|---|---|
| Vào STOP mode thật giữa các sự kiện | Dòng ngủ là yêu cầu then chốt (NFR-04). `WFI` thuần chưa phải STOP |
| Đánh thức bằng ngắt ngoài: PIR, VBUS, STATUS modem; bằng RTC cho lịch | Không cần polling theo chu kỳ |
| Không dùng tick 1 ms cố định trong lúc ngủ | Tick cố định làm MCU thức liên tục |
| Đánh thức bằng địa chỉ I2C nếu vi điều khiển hỗ trợ | `[CHƯA XÁC MINH]` trong reference manual; nếu không, dùng `MCU_IRQ` hai chiều hoặc thức theo chu kỳ khi SoC bật |
| Watchdog độc lập (IWDG) và phát hiện brown-out | Thiết bị ngoài trời không có người reset |
| ADC có hiệu chuẩn VREFINT và mạch chia áp | LFP có thể 3,65 V, cao hơn rail 3,3 V |
| Ngưỡng pin theo điện áp *có tải* | Điện áp LFP rất phẳng và sụt khi tải; ngưỡng đo ở giai đoạn 0 |
| Cắt sạc theo nhiệt độ là phần cứng độc lập | Firmware chỉ báo cáo, không là lớp an toàn duy nhất |
| Mọi chức năng chưa hiện thực phải trả lỗi rõ (không trả giá trị giả) | Tránh tình huống đo nhiệt độ luôn là 25 °C mà không ai biết |

### 2.3 Pin cạn

1. Điện áp có tải xuống dưới ngưỡng cảnh báo → đặt `LOW_BATT`, kéo `MCU_IRQ`.
2. SoC lưu việc đang làm, đóng file, báo `SOC_SHUTDOWN_DONE`.
3. MCU cắt `+5V_SOC` và `+5V_MODEM`, vào chế độ sinh tồn: chỉ thức khi có VBUS.
4. BMS cắt ở mức thấp hơn nữa (khoảng 2–2,5 V); MCU phải tắt hệ thống **trước** điểm này để không mất dữ liệu SD.

### 2.4 Nạp và cập nhật

- Prototype: SWD qua J_SWD.
- Production: kiểm tra bootloader hệ thống của dòng chip (UART/I2C) `[CHƯA XÁC MINH]`; cập nhật MCU từ SoC là mục tiêu sau.

### 2.5 Kiểm thử

Giữ mô hình HAL tách khỏi logic để chạy kiểm thử đơn vị trên máy tính (HAL giả). Bài học từ CAM4G: các stub (nhiệt độ, ADC) phải có kiểm thử thất bại nếu còn là stub.

## 3. Ứng dụng Linux trên SoC

### 3.1 Dịch vụ

| Dịch vụ | Việc |
|---|---|
| `powerd` | Máy trạng thái nguồn; nói chuyện với MCU qua I2C và `MCU_IRQ` |
| `camerad` | Lấy hình, mã hóa phần cứng |
| `recorderd` | Ghi đoạn lên SD |
| `modemd` | Lệnh AT, bật/tắt modem, theo dõi mạng |
| `uplinkd` | Hàng đợi sự kiện, MQTT, tải clip |
| `otad` | Cập nhật `[CHƯA XÁC MINH]` |

### 3.2 Máy trạng thái nguồn

Trạng thái: S0 Eco, S1 Watch, S2 Record, S3 Live, SF Fault (xem [01](01-kien-truc.md) §3).

| Sự kiện | Từ | Tới |
|---|---|---|
| PIR hoặc lịch | S0, S1 | S2 |
| Yêu cầu live | S0, S1, S2 | S3 |
| Hết thời gian live hoặc hủy | S3 | S2 |
| Hết thời gian ghi | S2 | Chế độ ngủ đã cấu hình (S0 nếu Eco, S1 nếu Watch) |
| Lỗi nhiệt hoặc pin cạn | bất kỳ | SF |
| Hết lỗi | SF | Chế độ ngủ đã cấu hình |

Giá trị mặc định (kế thừa từ CAM4G, điều chỉnh bằng cấu hình): clip 30 s, nghỉ trước khi ngủ 10 s, giữ live 120 s. Thiếu điều này là một lỗi của CAM4G: sau khi ghi nó luôn về ngủ sâu, nên không có chế độ Watch.

### 3.3 Ghi hình

- Dùng bộ mã hóa phần cứng của SoC (H.264/H.265) và đóng gói thành đoạn có container (MP4 phân mảnh hoặc MPEG-TS) `[CHƯA XÁC MINH]` API trong SDK. MJPEG thô chỉ để bring-up.
- An toàn khi mất điện: mỗi đoạn đóng đúng cách, mất tối đa một đoạn.
- Vòng ghi: xóa đoạn cũ khi đầy, giữ đoạn gắn với sự kiện.
- Thẻ nhớ chịu ghi cao; ghi nhận hao mòn.

### 3.4 Modem

- Lệnh AT qua UART; dữ liệu qua giao diện mạng USB (ECM/RNDIS) `[CHƯA XÁC MINH]` trên kernel của SDK. Phương án dự phòng: PPP qua UART, băng thông bị giới hạn ([05](05-ket-noi-va-cloud.md) §1).
- Mọi lệnh AT có thời gian chờ thực sự.
- Theo dõi: SIM, đăng ký mạng, cường độ sóng, băng tần.

### 3.5 Uplink

- MQTT QoS 1, hàng đợi lưu xuống đĩa, mỗi bản tin có ID duy nhất (tránh trộn bản tin trùng nội dung), lùi thời gian khi lỗi.
- Giới hạn kích thước hàng đợi; ưu tiên sự kiện hơn log.

### 3.6 Cấu hình và định danh

Định danh thiết bị, chứng chỉ và cấu hình lưu ở phân vùng riêng, không nằm trong image firmware.

### 3.7 OTA

Mục tiêu: phân vùng A/B cho rootfs, có quay lui. Khả năng của SDK Core1106 `[CHƯA XÁC MINH]` (O-08); đánh giá ở giai đoạn 0.

### 3.8 Chẩn đoán

Nhật ký vòng, tải lên theo yêu cầu; ghi số lần khởi động lại, lý do tắt, điện áp pin lúc tắt.

### 3.9 Kiểm thử

Kiểm thử đơn vị với đồng hồ và transport giả (đã có tiền lệ ở CAM4G), cộng kiểm thử tích hợp trên dev board ở giai đoạn 0 trước khi có board thật.
