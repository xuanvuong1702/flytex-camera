# Firmware MCU giám sát (STM32L0) — flytex-camera

Lõi firmware C99 cho MCU luôn-bật của board PWR: cấp/cắt nguồn SoC và modem,
bắt tay tắt máy an toàn, đo pin và nhiệt, giữ lịch thức, làm slave I2C cho SoC.

- Trạng thái: **chạy được trên host, có test**; port STM32L0 mới là khung,
  **chưa build và chưa kiểm chứng** (xem `hal/stm32l0/README.md`).
- Regmap sinh từ `spec/registers.toml` (giao thức 1.1); `regs_gen.h/.c` là file
  sinh, **không sửa tay**.
- Không có chỗ đánh dấu việc-dở trong đường chạy thật. Chỗ chưa làm thì trả lỗi
  rõ (`FLY_ENOSYS`) và ghi vào log vòng, không trả giá trị giả.

## 1. Bố cục

```
include/flytex/
  hal.h        bảng con trỏ hàm HAL + enum fly_pin + mã lỗi
  config.h     ngưỡng pin/nhiệt, thời gian chờ, chu kỳ lấy mẫu (có ghi nguồn)
  core.h       API công khai: fly_init/step/next_timeout_ms/run_slice/i2c/destroy
  ctx.h        trạng thái nội bộ fly_ctx_t (không phải API cho ứng dụng)
  regmap.h     đọc/ghi một byte thanh ghi
  power.h      máy trạng thái nguồn (nội bộ)
  battery.h    đo pin
  temp.h       nhiệt độ pin/môi trường
  sched.h      lịch WAKE_IN_S và kênh đánh thức WAKE_CHAN
  nvm.h        ảnh cấu hình bền (version + crc32)
  events.h     sự kiện, MCU_IRQ, byte STATUS/CHG/SYS_FLAGS/FAULT_CODE
  log.h        log vòng trong RAM
  regs_gen.h   (sinh) địa chỉ, bitfield, bảng fly_reg_descs
src/
  core.c regmap.c power.c battery.c temp.c sched.c nvm.c events.c log.c regs_gen.c
hal/host/      HAL giả: thời gian mô phỏng, chân đọc/ghi được, NVM RAM, stats
hal/stm32l0/   khung port thật, KHÔNG nằm trong build host
sim/           ffi.h/ffi.c — bề mặt ctypes cho mô phỏng Python
tests/         test.h, test_main.c, test_*.c, build.py
```

Không có biến toàn cục trong lõi và HAL: mọi trạng thái nằm trong `fly_ctx_t`
do `fly_init()` cấp phát. Ngoại lệ duy nhất là bảng hằng `fly_reg_descs` trong
file sinh. (Các file test dùng fixture `static` ở phạm vi file — đó là mã kiểm
thử, không phải firmware.)

## 2. Build và chạy test

```sh
python firmware/mcu/tests/build.py test    # build + chạy toàn bộ test host
python firmware/mcu/tests/build.py lib     # build build/flytexmcu.dll (Linux: libflytexmcu.so)
python firmware/mcu/tests/build.py clean
```

- Tìm compiler theo thứ tự: biến môi trường `CC`, rồi `cc`, `gcc`, `clang`.
- Cờ: `-std=c99 -Wall -Wextra -Werror -O1 -g -Ifirmware/mcu/include -Ifirmware/mcu/tests`.
  Build **sạch với `-Werror`** trên llvm-mingw (clang) ở Windows.
- Kết quả hiện tại: **59 test case, tất cả pass**, chia 9 file:
  regmap 15, nguồn 9, pin 5, nhiệt 6, lịch/kênh đánh thức 7, tickless 4,
  NVM 5, PIR 4, FFI 4.
- Build test có link thêm `sim/ffi.c` để phủ luôn bề mặt FFI; build `lib` cũng
  dùng đúng bộ nguồn đó.
- Output chỉ ASCII để console Windows không lỗi encoding.

Test dùng framework nhỏ trong `tests/test.h` (`TEST_CASE`, `TEST_ASSERT`,
`TEST_ASSERT_EQ`); mỗi case tự đăng ký bằng constructor, `tests/test_main.c`
chạy tất cả và in `PASS <tên>` / `PASS <số>` hoặc `FAIL ...`, exit code 0/1.

## 3. Vòng chạy tickless

```
fly_run_slice(ctx, max_ms):
  lặp:
    fly_step(ctx)                 # watchdog, đầu vào, pin, nhiệt, lịch, nguồn
    nếu đã trôi >= max_ms: thoát
    wait = fly_next_timeout_ms()  # 0 = có việc ngay, UINT32_MAX = không hẹn giờ
    enter_stop(min(wait, còn lại))# STOP thật, thức bởi PIR/VBUS/STATUS/RI/RTC/I2C
```

Không có `delay(1)`, không có counter 1 ms. Test đo: 24 giờ không sự kiện (ở
chế độ sinh tồn) chỉ vào STOP **1 lần**, `stop_ms` xấp xỉ 24 h; một giờ ở chế
độ Eco có khoảng 360 lần vào STOP (chu kỳ lấy mẫu 10 s), không phải 3,6 triệu.

`fly_next_timeout_ms()` **không** đưa watchdog vào danh sách hạn: nếu đưa vào
thì cứ 5 s phải thức một lần, phá vỡ yêu cầu ngủ dài. Watchdog được cho ăn
trong `fly_step()` khi đã quá 5 s. Hệ quả với IWDG thật ghi ở
`hal/stm32l0/README.md` §2.3 — đây là điểm **chưa chốt**, không phải đã xong.

## 4. Máy trạng thái nguồn

| Trạng thái | Nghĩa |
|---|---|
| `OFF` | SoC tắt, modem theo mode (Watch: bật, Eco: tắt) |
| `BOOT` | đã kéo `+5V_SOC`, chờ `SOC_READY` (hoặc `CMD SOC_WAKE`) tối đa 20 s |
| `ON` | SoC đang chạy |
| `SHUTDOWN` | đã đặt `EVENT.SHUTDOWN_REQ`, chờ `CMD SOC_SHUTDOWN_DONE` tối đa 10 s |
| `RETRY` | rail vừa cắt, chờ 500 ms rồi thử lại (tối đa 2 lần thử lại) |
| `SURVIVAL` | cắt hết rail, chỉ thức khi có VBUS; không lấy mẫu định kỳ |

- PIR, lịch (`WAKE_IN_S`), `WAKE_ALARM` → bật `+5V_SOC`.
- Quá hạn `SOC_READY` → `FAULT_CODE=SOC_NO_BOOT`; thử lại 2 lần rồi sinh tồn.
- `SOC_SHUTDOWN_DONE` → chờ thêm 500 ms rồi cắt rail. Quá 10 s → cắt cưỡng bức
  + `FAULT_CODE=SOC_NO_HANDSHAKE`.
- Pin dưới ngưỡng tắt → cắt ngay, sinh tồn + `BATT_UNDERVOLTAGE` (lỗi đang
  hoạt động, tự hết khi pin hồi phục). Có VBUS → thoát sinh tồn,
  `EVENT VBUS_CHANGE`.

## 5. Regmap

Hiện thực đúng `fly_reg_descs`:

- địa chỉ ngoài dải hoặc không định nghĩa → NACK (`FLY_EIO`);
- ghi thanh ghi `ro`, đọc thanh ghi `wo` → NACK;
- nhóm nhiều byte big-endian: đọc byte cao chốt cả nhóm, ghi byte cuối commit;
- `EVENT` xóa khi đọc; đọc xong thả `MCU_IRQ`;
- `MCU_IRQ` mức thấp khi `EVENT & EVENT_MASK` khác 0. `EVENT_MASK` reset là
  `0x3F`, nên mặc định `WAKE_ALARM` (bit 6) và `BUTTON` (bit 7) **không** kéo
  IRQ — đúng theo spec, muốn dùng phải bật mask;
- `CMD` lạ → `FAULT_CODE=BAD_CMD`, không làm gì; `CMD` hợp lệ: `SOC_WAKE`,
  `SOC_SHUTDOWN_DONE`, `MODEM_ON/OFF/RESET/PWRKEY`, `CLEAR_FAULT`;
- `MODE`/`WAKE_CHAN` sai giá trị → NACK (`FLY_EINVAL`), không đổi trạng thái.

## 6. Nhiệt độ, pin, NVM

- **Nhiệt**: `temp_c(0)` là NTC trên pack, `temp_c(1)` là DS18B20.
  `FLY_ENOSYS` (hoặc không có cảm biến) → thanh ghi trả **0x80** và
  `FAULT_CODE=SENSOR_STALE`; test khẳng định giá trị **khác 25**. Quá nóng
  > 45 °C → `BATT_OVERTEMP`, quá lạnh < 0 °C → `BATT_UNDERTEMP`, cả hai đặt
  `CHG.CHARGE_INHIBIT`, bit `SYS_FLAGS.CHG_INHIBIT` và kéo chân
  `FLY_PIN_CHG_INHIBIT`; hysteresis 2 °C. Không đọc được NTC thì cũng cấm sạc
  (hành vi an toàn), nhiệt độ môi trường thiếu chỉ ghi lỗi.
- **Pin**: `VBAT_MV = adc_mv × FLY_BATT_DIV_NUM / FLY_BATT_DIV_DEN` (mặc định
  2). Ngưỡng 3100/2900/3300 mV có hysteresis; `EVENT.LOW_BATT` chỉ một lần mỗi
  lần vượt ngưỡng. Đọc `0x06` chốt cả nhóm 2 byte.
- **NVM**: ảnh 16 byte có `version` + `crc32`. CRC hỏng hoặc sai version → nạp
  mặc định, `FAULT_CODE=NVM`, `boot_count=1`. NVM trắng (toàn `0xFF`) là máy
  mới, **không** đặt lỗi. Lưu: mode, wake_in_s, wake_chan, wake_period_s,
  boot_count.

## 7. Kênh đánh thức và chuyện TCP

- `WAKE_IN_S` đếm ngược theo thời gian thực; hết giờ → `EVENT SCHEDULE`, giá
  trị về 0, lưu NVM, đánh thức SoC.
- `WAKE_CHAN` định kỳ theo `WAKE_PERIOD_S` (0 → mặc định 900 s):
  - `MODEM_TCP_POLL`: bật rail modem, chờ `MODEM_STATUS` lên (tối đa 30 s, quá
    hạn → `FAULT_CODE=MODEM_NO_BOOT`), rồi đặt `EVENT WAKE_ALARM` và đánh thức
    SoC;
  - `SMS`: cạnh lên của `MODEM_RI` (J_B2B chân 21) đặt `WAKE_ALARM` và đánh
    thức SoC; ngoài ra vẫn có nhịp `WAKE_ALARM` định kỳ;
  - `EDRX_MQTT`: chỉ có nhịp `WAKE_ALARM` định kỳ, chưa có hành vi riêng.

**MCU không tự chạy TCP.** Nó chỉ bật rail modem và báo `WAKE_ALARM`; toàn bộ
TCP/TLS/MQTT nằm ở SoC (docs/14 §4.5, docs/15 §4). Không có chỗ nào trong
firmware giả vờ gửi/nhận dữ liệu mạng.

## 8. Khác biệt so với đặc tả (và lý do)

1. **`FLY_PIN_MODEM_RI = 4`** — input mới. Hợp đồng J_B2B và docs/15 §4.2 có
   tín hiệu RI (chân 21) để đánh thức bằng SMS; thiếu nó thì kênh Watch không
   có đường kiểm chứng. RI chỉ tạo `WAKE_ALARM` khi `WAKE_CHAN=SMS`; kênh khác
   bỏ qua để nhiễu chân không đánh thức hệ thống.
2. **`FLY_PIN_MODEM_RESET = 13`, `FLY_PIN_MODEM_PWRKEY = 14`** — hai chân ra
   mới, vì `CMD MODEM_RESET`/`MODEM_PWRKEY` cần chỗ phát xung. Mức tích cực để
   trong `config.h`, đánh dấu `[CHƯA XÁC MINH]`.
3. **Tham số `void *ctx` của HAL nhận chính con trỏ `fly_hal_t`.** `fly_init()`
   chỉ có một tham số nên không có chỗ truyền context riêng; HAL hiện thực đặt
   `fly_hal_t` là thành viên đầu tiên của struct trạng thái và ép kiểu ngược
   lại. Cách này giữ nguyên đúng chữ ký HAL đã chốt và không cần biến toàn cục.
4. **Thêm `include/flytex/ctx.h` và `power.h`** — `ctx.h` giữ trạng thái dùng
   chung giữa các module (đúng bố cục `src/` của docs/14 §2), `power.h` tách
   máy trạng thái nguồn khỏi `core.c`. Không đổi API công khai trong `core.h`.
5. **Build test có thêm `sim/ffi.c`** so với danh sách `src/ + hal/host/ +
   tests/`: nếu không, không có cách nào kiểm thử bề mặt FFI trong cùng một
   lần chạy. Build `lib` dùng đúng bộ nguồn như đặc tả.
6. **Watchdog không tạo wake** (xem §3). Yêu cầu "wdg_kick mỗi 5 s trong
   `fly_step`" và "24 giờ → rất ít lần vào STOP" chỉ cùng thỏa được nếu
   watchdog không lên lịch thức.
7. **Sinh tồn không lấy mẫu pin/nhiệt định kỳ.** Yêu cầu "chỉ thức khi VBUS"
   mâu thuẫn với "lấy mẫu ADC mỗi 10 s"; chọn đúng nghĩa sinh tồn. Khi có VBUS,
   thoát sinh tồn và lấy mẫu lại ngay.
8. **`WAKE_ALARM` cũng đánh thức SoC** (không chỉ đặt bit sự kiện). Kênh đánh
   thức chỉ có nghĩa nếu SoC được bật dậy; nếu chỉ đặt bit thì sự kiện nằm chờ
   vô ích.
9. **Khôi phục rail lúc `fly_init`**: Eco tắt cả hai rail, Watch bật modem.
   Rủi ro đã biết: nếu MCU reset (WDT) trong khi SoC đang chạy, việc cắt
   `+5V_SOC` ngay lúc khởi động có thể làm hỏng thẻ SD (docs/10 R-11). Phần cứng
   cũng có thể đã tự cắt khi GPIO về trạng thái reset; cần chốt bằng mạch giữ
   nguồn hoặc lưu "SoC đang chạy" vào NVM trước khi coi là an toàn.
10. **Đổi `MODE` chỉ áp rail modem khi SoC đang tắt**, để lệnh `MODE=ECO` không
    cắt modem của một SoC đang chạy.
11. **`CHG.CHARGING`/`CHARGE_DONE` luôn 0**: HAL không có tín hiệu CHRG/DONE
    (không nằm trong hợp đồng), nên firmware không bịa trạng thái sạc. Muốn có
    thì phải thêm chân vào HAL và bảng chân.
12. **`SYS_FLAGS.RTC_LOST` chưa hiện thực** (bit 5): chưa có phần đặt/kiểm giờ
    RTC. `SYS_FLAGS.CHG_INHIBIT` (bit 4) thì có, tính từ trạng thái cấm sạc.
13. **`WAKE_IN_S` bị kẹp ở 20 ngày** (`FLY_WAKE_IN_MAX_S`) để phép nhân ra ms
    không tràn `uint32_t`; giá trị lớn hơn bị kẹp chứ không NACK.
14. **Mỗi lần ghi `MODE`/`WAKE_CHAN`/`WAKE_IN_S`/`WAKE_PERIOD_S` đều ghi NVM**
    (đúng yêu cầu "lưu vào NVM"). Chưa có giảm mòn EEPROM; nếu SoC ghi cấu hình
    liên tục thì phải thêm debounce/đếm lần ghi.
15. **`hal_host` mặc định ADC = 1650 mV** (3,3 V sau chia) — giá trị bench để
    mô phỏng không rơi ngay vào sinh tồn; không phải số đo. Nhiệt độ mặc định
    là "không có cảm biến" để không che lỗi.

## 9. Những gì còn thiếu so với firmware thật

| Hạng mục | Trạng thái |
|---|---|
| Port STM32L0 chạy được | Khung, chưa build, chưa kiểm chứng (`hal/stm32l0/`) |
| SDK/driver: GPIO, RTC, ADC, I2C slave, EEPROM, IWDG | Chỉ mô tả thanh ghi, chưa có mã chạy thật |
| ISR I2C gọi `fly_i2c_read/write` | Chưa có |
| Đọc NTC (bảng tra) và DS18B20 (1-Wire) | `temp_c()` trả `FLY_ENOSYS` |
| Ghi EEPROM | `nvm_write()` trả `FLY_ENOSYS` |
| Đặt giờ RTC từ SoC, `RTC_LOST` | Chưa có |
| OTA firmware MCU | Chưa có (docs/04 §2.4) |
| Đo dòng ngủ thật, đo điểm cắt nhiệt | Chưa có board (docs/08) |

## 10. Ghi chú cho mô phỏng Python

`build/flytexmcu.dll` (hoặc `.so`) xuất đúng các hàm trong `sim/ffi.h`. Khi
dùng ctypes, đặt `restype`/`argtypes` cho mọi hàm — đặc biệt `fsim_new` trả
`c_void_p` và `fsim_free` nhận `c_void_p`, nếu không Python sẽ cố ép con trỏ
64-bit sang `int` và báo `OverflowError`.

```python
import ctypes
lib = ctypes.CDLL("firmware/mcu/build/flytexmcu.dll")
lib.fsim_new.restype = ctypes.c_void_p
lib.fsim_free.argtypes = [ctypes.c_void_p]
h = lib.fsim_new()
...
lib.fsim_free(h)
```

`fsim_stats_json()` trả chuỗi JSON tĩnh trong handle, dạng
`{"stop_entries":5,"stop_ms":3600000,"wdg_kicks":10,"i2c_nacks":0,"steps":42}`.
`i2c_nacks` do lớp gọi đếm khi lõi trả lỗi; `steps` lấy từ bộ đếm trong lõi;
`stop_entries`/`stop_ms`/`wdg_kicks` do HAL host đếm.
