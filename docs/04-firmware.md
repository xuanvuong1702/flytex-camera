# 04 — Firmware

- Trạng thái: v1.1, cập nhật theo mã trong repo
- Ngày: 2026-11-09

## 1. Phạm vi

Hai khối firmware: **MCU giám sát** (luôn bật, C, STM32L0) và **ứng dụng Linux** trên SoC (Python, một tiến trình nhiều module). Giao thức giữa chúng ở [15](15-giao-thuc-va-cloud.md) §2 và sinh từ `spec/registers.toml`.

Trong repo này, cả hai khối đã có lõi chạy được trên máy tính, có test; phần chạm phần cứng (port STM32L0, RK MPI, I2C thật) còn là khung hoặc lớp mỏng chưa kiểm chứng. Kiến trúc module ở [14](14-kien-truc-phan-mem.md).

## 2. MCU giám sát

### 2.1 Nhiệm vụ

- Cấp và cắt nguồn cho SoC và modem; thực hiện bắt tay tắt máy an toàn.
- Nhận PIR, lịch, cắm/rút USB-C, trạng thái modem, **RI** (SMS đến).
- Đo điện áp pin và nhiệt độ; báo lên SoC qua I2C.
- Giám sát pin cạn.
- Làm slave I2C, kéo `MCU_IRQ`.

### 2.2 Yêu cầu hiện thực

| Yêu cầu | Lý do | Trạng thái trong mã |
|---|---|---|
| Vào STOP mode thật giữa các sự kiện | Dòng ngủ là yêu cầu then chốt (NFR-04). `WFI` thuần chưa phải STOP | Có: `fly_run_slice` chỉ gọi `hal->enter_stop`; HAL host đếm số lần vào STOP |
| Đánh thức bằng ngắt ngoài: PIR, VBUS, modem STATUS/RI; bằng RTC cho lịch | Không cần polling theo chu kỳ | Có ở lớp lõi; chân thật thuộc port STM32L0 |
| Không dùng tick 1 ms cố định trong lúc ngủ | Tick cố định làm MCU thức liên tục | Có: test 24 giờ không sự kiện kiểm số lần vào STOP |
| Đánh thức bằng địa chỉ I2C | SoC là master, MCU là slave | `[CHƯA XÁC MINH]`: STM32L0 có tính năng wakeup on address match; phải xác nhận trên silicon |
| Watchdog độc lập (IWDG) và phát hiện brown-out | Thiết bị ngoài trời không có người reset | Có ở HAL interface; chưa có port thật |
| ADC có hiệu chuẩn VREFINT và mạch chia áp | LFP có thể 3,65 V, cao hơn rail 3,3 V | Hệ số chia trong `config.h`; hiệu chuẩn thuộc port |
| Ngưỡng pin theo điện áp *có tải* | Điện áp LFP rất phẳng và sụt khi tải | Có ngưỡng cảnh báo/tắt/khôi phục, có hysteresis; số phải đo lại ở G0 |
| Cắt sạc theo nhiệt độ là phần cứng độc lập | Firmware chỉ báo cáo, không là lớp an toàn duy nhất | Có: firmware đọc và báo `CHARGE_INHIBIT` |
| Mọi chức năng chưa hiện thực phải trả lỗi rõ (không trả giá trị giả) | Tránh tình trạng đo nhiệt độ luôn là 25 °C mà không ai biết | Có: `FLY_ENOSYS` → 0x80 + `SENSOR_STALE`; có test khẳng định |

Hai điểm còn mở ở port STM32L0, đã ghi thành rủi ro:

- **IWDG trong STOP (chốt tạm 2026-11-09):** tắt IWDG ngay trước khi vào STOP và bật lại sau khi thức; ghi nhận đây là đánh đổi có chủ đích (mất bảo vệ watchdog trong lúc ngủ sâu, bù bằng brown-out và RTC/PIR wake). Đo lại M-02; nếu cần watchdog cả trong ngủ thì chuyển sang thức 20 s để kick và giảm tần suất lấy mẫu pin. Xem R-32.
- **MCU reset khi SoC đang chạy:** `fly_init` cắt `+5V_SOC` ngay theo trạng thái đã khôi phục, có thể làm hỏng thẻ. Cần mạch giữ nguồn hoặc cờ "SoC đang chạy" trong NVM trước khi coi là an toàn. Xem R-31.

### 2.3 Pin cạn

1. Điện áp có tải xuống dưới ngưỡng cảnh báo → đặt `LOW_BATT`, kéo `MCU_IRQ`.
   - Ngưỡng LFP (2026-11-09): cảnh báo **3,05 V**, cắt **2,90 V**, khôi phục **3,20 V**.
   - Cảnh báo dùng mẫu thô và phải giữ **6 mẫu** (60 s); cắt **3 mẫu** (30 s); khôi phục **12 mẫu** (120 s). EMA 1/2 vẫn được tính để log nhưng không quyết định ngưỡng, tránh trễ 6–10 mẫu.
   - Số này vẫn phải đo lại ở G0 (M-01/M-02); điện áp LFP sụt theo tải nên ngưỡng phải xét trạng thái tải.
2. SoC lưu việc đang làm, đóng file, báo `SOC_SHUTDOWN_DONE`.
3. MCU cắt `+5V_SOC` và `+5V_MODEM`, vào chế độ sinh tồn: chỉ thức khi có VBUS.
4. BMS cắt ở mức thấp hơn nữa (khoảng 2–2,5 V); MCU phải tắt hệ thống **trước** điểm này để không mất dữ liệu SD.

### 2.4 Nạp và cập nhật

- Prototype: SWD qua J_SWD.
- Production: kiểm tra bootloader của dòng chip `[CHƯA XÁC MINH]`; cập nhật MCU từ SoC là mục tiêu sau.
- SoC: nạp qua pad dịch vụ/mux USB hoặc thẻ SD, vì modem chiếm cổng USB duy nhất ([03](03-giao-dien.md) §4.1).

### 2.5 Kiểm thử

Mô hình HAL tách khỏi logic để chạy test đơn vị trên máy tính. Test host kiểm cả những thứ dễ giả: nhiệt độ thiếu cảm biến, ADC không có hệ số chia, tickless, CRC NVM hỏng, bắt tay tắt máy quá hạn.

```powershell
python firmware/mcu/tests/build.py test
```

Bài học từ CAM4G: stub (nhiệt độ, ADC) phải có test thất bại nếu còn là stub. Trong bản này, test `temperature_missing_sensor` đỏ nếu ai đó trả 25 °C.

## 3. Ứng dụng Linux trên SoC

### 3.1 Dịch vụ

Một tiến trình `flytex-device` gồm các module, tách ranh giới để có thể thành daemon sau này. Lý do ở [14](14-kien-truc-phan-mem.md) §4.1.

| Module (thay cho tên cũ) | Việc |
|---|---|
| `power` (powerd) | Máy trạng thái nguồn; nói chuyện với MCU qua I2C và `MCU_IRQ` |
| `media` (camerad) | Lấy hình, mã hóa phần cứng — chưa có mã thật, xem §3.3 |
| `recorder` (recorderd) | Ghi đoạn lên thẻ, an toàn khi mất điện |
| `modem` (modemd) | Lệnh AT, bật/tắt modem, theo dõi mạng |
| `uplink` (uplinkd) | Hàng đợi sự kiện bền, MQTT, tải clip |
| `cloud`, `commands` | MQTT, xử lý lệnh và ack |
| `identity`, `config`, `diagnostics` | Định danh, cấu hình, log |
| OTA (`otad`) | `OtaManager`: tải, xác minh sha256 + chữ ký, cài A/B, quay lui; thiếu bộ xác minh thì từ chối (`NOT_IMPLEMENTED`) |

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

Giá trị mặc định: clip 30 s, nghỉ trước khi ngủ 10 s, giữ live 120 s. Thiếu điều này là một lỗi của CAM4G: sau khi ghi nó luôn về ngủ sâu, nên không có chế độ Watch. Test `test_returns_to_configured_mode` khẳng định không tái diễn.

### 3.3 Ghi hình

- Mỗi clip chia thành đoạn có giới hạn thời gian và kích thước.
- Ghi `.part`, `fsync`, đóng, rồi `rename` — mất điện tối đa một đoạn. Chỉ mục JSONL append + fsync; khởi động lại thì `recover()` dọn `.part` mồ côi.
- Vòng ghi: xóa clip cũ khi đầy; clip gắn sự kiện được `pin`, có trần riêng để thẻ không đầy.
- **Container: MPEG-TS H.264** (`app/flytex/tsmux.py`), có PAT/PMT, PCR, PTS 90 kHz, lặp PSI; test kiểm bằng parser độc lập. `RawMuxer` chỉ để bring-up và bị từ chối khi `allow_raw_muxer=False`. Chưa thử với dữ liệu camera thật `[CHƯA XÁC MINH]`.
- Clip được đưa vào `UploadSpool` và tải lên kho bằng HTTPS PUT; nhiều đoạn TS được nối thành một file trước khi tải.
- Nguồn hình thật dùng RK MPI của SDK; trong repo chỉ có nguồn giả và lớp `RkMpiSource` trả `NotImplementedError` kèm hướng dẫn.

### 3.4 Modem

- Lệnh AT qua UART; dữ liệu qua giao diện mạng USB (ECM/RNDIS) `[CHƯA XÁC MINH]` trên kernel của SDK. Phương án dự phòng: PPP qua UART, băng thông bị giới hạn.
- Mọi lệnh AT có deadline tuyệt đối; transport treo thì trả `AtTimeout`, không treo tiến trình. URC được tách khỏi kết quả lệnh.
- Theo dõi: SIM, đăng ký mạng, cường độ sóng, băng tần.
- Kênh đánh thức: xem [15](15-giao-thuc-va-cloud.md) §4; MCU giữ chân RI, SoC đọc SMS sau khi thức.

**Rủi ro chi phí và replay của SMS (2026-11-09, chưa sửa):** MCU bật SoC khi RI kéo, trước khi token được kiểm; SMS rác hoặc cuộc gọi đến có thể đánh thức nhiều lần; token hiện là chuỗi tĩnh, có thể replay. Kế hoạch bắt buộc trước G0:

1. MCU giới hạn tần suất: tối đa một lần bật SoC mỗi 10 phút do RI, kể cả khi token sai.
2. Token dạng `W <timestamp> <hmac16>`; SoC kiểm HMAC-SHA256 bằng khóa thiết bị, từ chối timestamp lệch quá 10 phút và ghi nhớ nonce để chống replay.
3. Nếu modem cho đọc số gửi trước khi bật SoC (cần UART phụ, O-12), thêm whitelist số.
4. Đo chi phí một lần đánh thức (M-35) và đưa vào ngân sách pin.

**Đã hiện thực một phần (2026-11-09):** SoC kiểm HMAC-SHA256, timestamp ±10 phút, chống replay và lưu mốc xuống `wake_last_ts`; từ chối nếu chưa cấu hình `wake_secret`. **Chưa hiện thực:** giới hạn tần suất ở MCU và whitelist số gửi — vẫn là blocker của vòng 7 trong [17](17-san-sang-prototype.md).
- Tên lệnh cụ thể (`AT+QNETDEVCTL` hay tương đương) phải đối chiếu datasheet EC200U `[CHƯA XÁC MINH]`.

### 3.5 Uplink

- MQTT QoS 1, hàng đợi lưu xuống đĩa, mỗi bản tin có ID duy nhất; lùi thời gian khi lỗi, có jitter và trần.
- Giới hạn kích thước hàng đợi; ưu tiên `fault` > `motion` > `status` > `battery`/`temp`; khi đầy thì bỏ bản tin ưu tiên thấp nhất và ghi log.

### 3.6 Cấu hình và định danh

Định danh thiết bị, chứng chỉ và cấu hình lưu ở phân vùng riêng, không nằm trong image firmware. Ghi cấu hình theo kiểu nguyên tử (file tạm + `rename`).

### 3.7 OTA

Phần mềm: `app/flytex/ota.py` hiện thực máy trạng thái `stage → activate → check_boot → healthy/rollback`, có lưu trạng thái xuống đĩa và test. Image phải khớp `sha256`, đúng kích thước, và qua `Verifier` chữ ký; chưa cấu hình verifier thì từ chối cập nhật, không "tạm chấp nhận".

Phần thiết bị: phân vùng A/B thật, ghi eMMC, đổi cờ boot và reboot do `Installer` lo — **chưa có** vì phụ thuộc SDK Core1106 `[CHƯA XÁC MINH]` (O-08). Đánh giá ở giai đoạn 0.

### 3.8 Chẩn đoán

Log vòng, tải lên theo yêu cầu; ghi số lần khởi động lại, lý do tắt, điện áp pin lúc tắt. Không ghi khóa, token, nội dung SMS.

### 3.9 Kiểm thử

Kiểm thử đơn vị với đồng hồ và transport giả, cộng mô phỏng tích hợp dùng **chính firmware C** qua FFI. Chạy toàn bộ:

```powershell
python run_tests.py
```

Chưa có test nào chạy trên thiết bị thật; mục M-41 trong [08](08-kiem-chung.md) là việc phải làm khi có board.
