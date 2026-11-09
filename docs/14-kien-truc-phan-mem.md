# 14 — Kiến trúc phần mềm

- Trạng thái: Bản triển khai v0.2 (đi kèm mã trong repo)
- Ngày: 2026-11-09
- Phạm vi: firmware MCU, ứng dụng Linux trên SoC, hợp đồng cloud, công cụ đo và mô phỏng.

Tài liệu này là hợp đồng giữa các module. Số liệu nguồn nằm ở nơi khác: regmap ở [spec/registers.toml](../spec/registers.toml), connector ở [spec/b2b.toml](../spec/b2b.toml), MQTT ở [spec/mqtt.toml](../spec/mqtt.toml). Không chép lại giá trị ở đây.

## 1. Nguyên tắc hiện thực

1. **Nguồn sự thật máy đọc được.** Regmap, pinout, MQTT đều nằm trong `spec/`. Mã C, mã Python và bảng tài liệu đều sinh từ đó bằng `python spec/generate.py`. Sửa tay file sinh là lỗi CI.
2. **Transport tiêm được.** Không module nào tự mở `/dev/i2c`, tự gọi `sleep`, hay tự đọc đồng hồ hệ thống. Mọi thứ đi qua interface để test được trên máy tính không có phần cứng.
3. **Không có stub giả.** Chức năng chưa làm phải trả lỗi rõ (`NotImplementedError`, `-ENOSYS`, `NOT_IMPLEMENTED`), không trả 0, không trả 25 °C, không giả vờ thành công.
4. **Thời gian là tham số.** MCU dùng lịch không tick; ứng dụng Linux nhận `Clock`. Test dùng đồng hồ giả nên chạy tức thì và không flaky.
5. **Mỗi lỗi có mã.** Không nuốt exception. Lỗi được ghi vào log vòng và, nếu đáng kể, vào `FAULT_CODE`.

## 2. Bố cục mã

```
spec/                    spec/*.toml, generate.py, generated/
firmware/mcu/
  include/flytex/        hal.h, core.h, config.h, regs_gen.h (sinh)
  src/                   core, regmap, power, battery, temp, sched, nvm, log, regs_gen.c (sinh)
  hal/host/              HAL giả cho test host và cho thư viện mô phỏng
  hal/stm32l0/           port thật, chỉ build khi có SDK; chưa kiểm chứng
  tests/                 test host (C) + build.py
  sim/                   FFI C cho mô phỏng Python
app/flytex/              gói Python chạy trên SoC
  regs_gen.py, mqtt_gen.py (sinh)
  clock.py mcu.py power.py modem.py media.py recorder.py uplink.py
  cloud.py commands.py identity.py config.py diagnostics.py service.py cli.py
app/tests/               unittest, chạy được không cần phần cứng
sim/                     kịch bản end-to-end: firmware C (ctypes) + app Python + modem giả
tools/measure/           nhập số đo G0, sinh báo cáo năng lượng
tools/docs_check/        kiểm tra tham chiếu ID và bảng mục lục
```

## 3. Firmware MCU

### 3.1 HAL

HAL là một bảng con trỏ hàm, không có biến toàn cục. Mỗi hàm nhận `void *ctx`, và `ctx` chính là con trỏ tới bảng `fly_hal_t` (HAL đặt bảng này là thành viên đầu của struct trạng thái riêng). Mọi hàm trả `0` khi thành công, số âm khi lỗi.

| Hàm | Ngữ nghĩa |
|---|---|
| `uint32_t millis(ctx)` | Đồng hồ đơn điệu, ms, tràn sau 49 ngày |
| `uint32_t enter_stop(ctx, max_ms)` | Vào STOP, trả về bitmask nguồn đánh thức; `max_ms = 0` là không hẹn giờ |
| `int gpio_read(ctx, id)` | Đọc mức chân, `id` theo `enum fly_pin` |
| `void gpio_write(ctx, id, level)` | Đặt mức chân ra |
| `int adc_mv(ctx, ch, *mv)` | Đọc ADC đã hiệu chuẩn, mV |
| `int temp_c(ctx, sensor, *c)` | Nhiệt độ; `-ENOSYS` nếu cảm biến không có |
| `int nvm_read/write(ctx, off, buf, len)` | Bộ nhớ cấu hình, ghi phải bền qua mất điện |
| `void wdg_kick(ctx)` | Cho watchdog ăn |
| `uint64_t epoch_s(ctx)` | Giờ thực, nếu có RTC |
| `uint8_t reset_cause(ctx)` | Nguyên nhân reset, cùng bố cục bit với `SYS_FLAGS` |

`enter_stop` là điểm khác biệt giữa bản này và CAM4G: nó phải thật sự vào STOP, không chỉ `WFI`. Test host kiểm bằng bộ đếm số lần vào STOP và khẳng định không có tick định kỳ.

### 3.2 Vòng chạy

```
khởi tạo → đọc NVM → khôi phục mode, lịch, boot count
lặp:
  flytex_step()                  # xử lý sự kiện đã có, tính timeout kế tiếp
  flytex_next_timeout_ms()       # 0 nếu có việc phải làm ngay
  enter_stop(timeout)            # thức bởi PIR, VBUS, modem STATUS, RTC, hoặc I2C
```

Không có `while(1)` với `delay(1)`. Không có counter 1 ms.

### 3.3 Regmap

Hiện thực đúng bảng sinh từ `spec/registers.toml`:

- kiểm tra quyền truy cập bằng bảng `fly_reg_descs`;
- `EVENT` xóa khi đọc;
- nhóm nhiều byte big-endian, latch khi đọc byte cao, commit khi ghi byte cuối;
- `CMD` mã lạ: đặt `FAULT_CODE = BAD_CMD`, không thực hiện gì;
- địa chỉ ngoài dải hoặc undefined: NACK.

### 3.4 Chính sách pin và nhiệt

Ngưỡng nằm trong `config.h`, có ghi chú nguồn. Điện áp pin đọc từ ADC qua mạch chia; hệ số chia là bắt buộc, vì LFP có thể 3,65 V cao hơn rail 3,3 V.

- Dưới ngưỡng cảnh báo có tải → `LOW_BATT`, kéo `MCU_IRQ`, yêu cầu SoC tắt an toàn.
- Dưới ngưỡng tắt → cắt rail, vào sinh tồn, chỉ thức khi có VBUS.
- Cắt sạc do nhiệt là phần cứng; firmware chỉ đọc và báo `CHARGE_INHIBIT`. Firmware **không** được coi mình là lớp an toàn duy nhất.
- Nhiệt độ không đọc được → `0x80`, `FAULT_CODE = SENSOR_STALE`, không trả 25 °C.

## 4. Ứng dụng Linux

### 4.1 Tiến trình và dịch vụ

Một tiến trình `flytex-device` chứa các module, thay vì sáu daemon riêng, vì SoC chỉ có 256 MB RAM và các module chia sẻ trạng thái nguồn. Ranh giới module vẫn giữ để tách được thành daemon sau này nếu cần.

| Module | Trách nhiệm | Interface chính |
|---|---|---|
| `clock` | Thời gian | `Clock.now()`, `Clock.monotonic()`, `Clock.sleep(s)` |
| `mcu` | Giao tiếp MCU | `McuLink.read(addr, n)`, `.write(addr, data)`, `.irq_wait(timeout)` |
| `power` | Máy trạng thái nguồn | `PowerController.tick(now)`, `.on_event(mask)`, `.request_live(s)` |
| `modem` | AT, mạng, kênh đánh thức | `AtClient.command(cmd, timeout)` |
| `media` | Nguồn hình | `MediaSource.start/read_frame/stop` |
| `recorder` | Ghi đoạn lên thẻ | `SegmentRecorder.start/write/stop/pin/evict` |
| `uplink` | Hàng đợi bền | `UplinkQueue.enqueue/peek/mark_sent/retry_later` |
| `cloud` | MQTT | `Publisher.connect/publish/subscribe/loop` |
| `commands` | Lệnh từ cloud | `CommandRouter.dispatch(topic, payload) -> Ack` |
| `identity` | Định danh và chứng chỉ | `Identity.load(root)`, `.device_id`, `.cert_paths` |
| `config` | Cấu hình | `Config.load/save`, `Config.set_allowed(key, value)` |
| `diagnostics` | Log vòng, lý do khởi động | `Diagnostics.log()`, `.record_boot()` |
| `service` | Ghép tất cả | `DeviceService.boot()`, `.run_forever()`, `.step(now)` |

### 4.2 Máy trạng thái nguồn

Giống [04](04-firmware.md) §3.2 nhưng là mã thật, có test:

- `S0 Eco`, `S1 Watch`, `S2 Record`, `S3 Live`, `SF Fault`;
- sau khi hết clip quay về **chế độ ngủ đã cấu hình**, không mặc định về Eco (lỗi của CAM4G);
- `S3` có timeout; hết giờ thì về `S2` rồi mới ngủ;
- lỗi nhiệt hoặc pin cạn vào `SF`, thoát khi điều kiện hết;
- `mode.set` bị từ chối khi đang ghi (`BUSY`).

**Cắt rail khi ngủ.** Về `S0`/`S1` trong phần mềm không có nghĩa là SoC đã tắt: rail vẫn do MCU giữ. Vì vậy `PowerController` gọi hook `on_sleep` khi đã đóng file xong; `DeviceService` dùng hook này để gửi `CMD = SOC_SHUTDOWN_DONE` rồi dừng tiến trình, và MCU cắt `+5V_SOC`. Thiếu bước này, thiết bị "ngủ" mà vẫn tiêu 30–80 mA, phá mục tiêu pin. Hook có test riêng.

### 4.3 Ghi hình

- Mỗi clip chia thành đoạn có giới hạn thời gian và kích thước.
- Ghi vào `.part`, `fsync`, đóng container, rồi `rename` — mất điện tối đa một đoạn.
- Chỉ mục clip là file JSONL append, có `fsync`; khi khởi động, dọn `.part` mồ côi và sửa chỉ mục.
- Clip gắn sự kiện được `pin`, không bị vòng ghi xóa; có giới hạn để thẻ không đầy.
- Nguồn hình thật dùng RK MPI của SDK; trong repo chỉ có nguồn giả và một lớp `RkMpiSource` trả `NotImplementedError` kèm hướng dẫn. **Chưa có mã chạy camera thật.**

### 4.4 Uplink

- Bản tin có `id` duy nhất 16 hex; hàng đợi lưu xuống đĩa, append + `fsync`.
- Không gộp bản tin khác nội dung; chỉ bỏ khi đã gửi và đã `ack` (QoS 1).
- Lùi thời gian có jitter, trần cấu hình; ưu tiên `fault` > `motion` > `status` > `battery`/`temp`.
- Giới hạn kích thước; khi đầy, bỏ bản tin ưu tiên thấp nhất và ghi log, không bỏ im lặng.

### 4.5 Modem

- Một lệnh AT một deadline tuyệt đối; đọc có timeout thật, không dựa vào việc transport tự trả.
- URC được tách khỏi kết quả lệnh; URC đến giữa lệnh không làm hỏng parse.
- Chuỗi khởi động: PWRKEY theo datasheet, chờ `RDY`, kiểm SIM, đăng ký, APN, kiểm tra interface dữ liệu.
- Kênh đánh thức khi ngủ dùng TCP stack của modem (xem [15](15-giao-thuc-va-cloud.md) §4). Đây là chỗ bản nháp v0.1 mô tả "eDRX + MQTT" trong khi SoC đã tắt — không hiện thực được; nay chốt lại.

### 4.6 Bảo mật

- TLS mọi kết nối; chứng chỉ riêng từng thiết bị nằm ở phân vùng định danh, không nằm trong image.
- Không mật khẩu mặc định dùng chung.
- OTA phải có chữ ký; hiện chưa hiện thực, `ota.start` trả `NOT_IMPLEMENTED`.

## 5. Phân vùng lưu trữ trên thiết bị

| Đường dẫn | Nội dung | Ghi chú |
|---|---|---|
| `/data/identity/` | Device ID, khóa, chứng chỉ | Cấp lúc sản xuất, chỉ đọc với tiến trình |
| `/data/config.json` | Cấu hình | Ghi nguyên tử: file tạm + `rename` |
| `/data/queue.jsonl` | Hàng đợi uplink | Append + `fsync` |
| `/data/clips/` | Clip và chỉ mục | Vòng ghi, clip gắn sự kiện được giữ |
| `/data/diag/` | Log vòng, lý do khởi động | Giới hạn kích thước |

Thẻ nhớ là điểm hỏng dữ liệu khi mất điện; mọi lần ghi đều phải chịu được mất điện ở bất kỳ byte nào.

## 6. Kiểm thử

| Tầng | Cách chạy | Phạm vi |
|---|---|---|
| Spec | `python -m unittest discover -s spec/tests` | Sinh mã khớp spec, không chồng địa chỉ, pinout đủ dòng |
| Hardware | `python hardware/calc/tests/test_pwr.py` | Dòng boost, hồi tiếp, NTC, ADC, nhiệt, kiểm tra đạt/không |
| Firmware | `python firmware/mcu/tests/build.py test` | Regmap, state machine, pin, nhiệt, bắt tay, STOP |
| Ứng dụng | `python -m unittest discover -s app/tests -t .` | Máy trạng thái, AT timeout, hàng đợi, ghi, lệnh |
| Mô phỏng | `python sim/run.py --scenario all` | Firmware C thật + app thật + modem/cloud giả |
| Tài liệu | `python tools/docs_check/check.py` | Tham chiếu ID, mục lục, file sinh lệch |
| Tất cả | `python run_tests.py` | 23 bước: spec, hardware, firmware, app, tools, CLI, sim |

Số test hiện tại: spec 29, hardware 28, firmware 59, ứng dụng 125, công cụ 108. Tổng 349 test cộng 5 kịch bản mô phỏng. Không test nào cần phần cứng.

Test cần phần cứng nằm ở [08](08-kiem-chung.md) và vẫn là "Chưa làm".

## 7. Việc chưa làm, có chủ đích

| Hạng mục | Trạng thái | Điều kiện làm |
|---|---|---|
| Mã chạy camera thật (RK MPI) | Chưa có | Có SDK và dev board ở G0 |
| Mã chạy I2C thật trên SoC | Có lớp mỏng, chưa thử phần cứng | Có board CMP |
| Port STM32L0 thật | Khung, chưa build | Có SDK và board PWR |
| OTA có chữ ký | Chưa có | Chốt cơ chế A/B ở G0 |
| MQTT TLS thật | Lớp mỏng trên paho, chưa thử | Có chứng chỉ thiết bị |
| Relay video | Chỉ hợp đồng, chưa cấu hình | Chọn MediaMTX và đo ở G0 |
