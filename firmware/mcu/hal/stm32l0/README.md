# Port STM32L0 — khung, **chưa build, chưa kiểm chứng**

- Trạng thái: khung mã, **chưa biên dịch cho target**, chưa chạy trên board PWR.
- Điều kiện để coi là "xong": có SDK/board, build được, đo dòng ngủ, đo điểm cắt
  nhiệt, và chạy được bộ test host trên phần cứng thật (docs/14 §7).

File `port_stm32l0.c` chỉ được biên dịch khi định nghĩa `FLYTEX_TARGET_STM32L0`.
`tests/build.py` không liệt kê file này, nên nó **không lọt vào build host**.
Khi không có macro, file chỉ còn một typedef rỗng.

## 1. Những thanh ghi/API khung này dùng

| Việc | Thanh ghi / API | Ghi chú |
|---|---|---|
| Vào STOP | `PWR->CR` (`LPSDSR`, `PDDS=0`, `CWUF`, `CSBF`), `SCB->SCR.SLEEPDEEP`, `WFI` | STOP 1, không phải Standby |
| Hẹn giờ thức | `RCC->CSR.RTCSEL=LSI`, `RTC->CR.WUTE/WUCKSEL`, `RTC->WUTR`, `RTC->ISR.WUTWF/WUTF`, `RTC->PRER`, `EXTI` line 20 | LSI ~37 kHz; WUCKSEL=/16 cho ≤28 s (ms), ck_spre 1 Hz cho >28 s; PRER A=127/S=255 |
| Thời gian ms | `RTC->TR/DR/SSR/PRER` (BCD) | SysTick dừng trong STOP nên **không** dùng SysTick làm gốc thời gian |
| Chân | `GPIOx->MODER/IDR/BSRR/BRR` | Bảng chân là chỗ giữ chỗ, xem §4 |
| ADC pin | `ADC1->CHSELR/CR/ISR/DR`, `ADC_CCR.VREFEN`, `VREFINT_CAL` ở `0x1FF80078` | `VDDA = 3000 mV × CAL / RAW`, rồi `mV = raw × VDDA / 4095`; lõi tự nhân hệ số chia |
| IWDG | `IWDG->KR` (`0xCCCC` start, `0x5555` unlock, `0xAAAA` reload), `PR`, `RLR` | **Mặc định tắt** (`FLY_IWDG_ENABLE=0`); nếu bật, STOP phải < ~28 s |
| I2C slave | `I2C1->CR1.PE`, `CR1.WUPEN`, `OAR1` = `0x30 << 1`, `TIMINGR`, `ISR/ICR/RXDR/TXDR` | WUPEN = đánh thức khỏi STOP bằng địa chỉ, **chưa xác minh** |
| NVM | EEPROM dữ liệu `0x08080000`, mở khóa `FLASH->PEKEYR` | `nvm_write` đang trả `FLY_ENOSYS` |
| Nguyên nhân reset | `RCC->CSR` (`IWDGRSTF`, `PORRSTF`, `LPWRRSTF`, `PINRSTF`, `SFTRSTF`, `OBLRSTF`) | ánh xạ sang `SYS_FLAGS` như bảng dưới |

## 2. Những điểm phải xác minh trước khi tin

1. **Địa chỉ/bit cụ thể** đánh dấu `[CHƯA XÁC MINH]` trong mã. Reference manual
   của đúng mã chip là nguồn duy nhất; nhiều dòng L0 khác nhau ở `PWR`, `RCC`,
   `ADC_CCR`.
2. **WUPEN**: một số tài liệu nói I2C có thể đánh thức khỏi STOP khi nhận đúng
   địa chỉ, một số nói chỉ ngắt mới đánh thức được. Đây là câu hỏi mở của
   docs/04 §2.2. Nếu sai, phải quay lại phương án `MCU_IRQ` hai chiều hoặc
   thức theo chu kỳ khi SoC bật.
3. **IWDG trong STOP**: đã chốt cho prototype là **không khởi động IWDG**
   (`FLY_IWDG_ENABLE=0`). Nếu bật, IWDG vẫn đếm trong STOP và giới hạn thời gian
   ngủ dưới ~28 s; khi đó phải giảm `max_ms` hoặc thức định kỳ để kick. Quyết
   định này phải đo lại ở M-02; nếu cần watchdog khi ngủ, dùng kiến trúc thức
   20 s/lần.
4. **RI (MODEM_RI)**: `fly_step` chỉ lấy mẫu mức, nên xung RI rất ngắn có thể bị
   bỏ. Port thật phải cấu hình EXTI cho chân RI và **chốt cờ** trong ISR, để
   lần `fly_step` kế tiếp còn thấy cạnh lên.
5. **ADC kênh 1** cho chân chia áp VBAT và **bảng chân** trong `pin_map()` là
   chỗ giữ chỗ; phải lấy từ schematic PWR.
6. **Nhiệt độ**: `temp_c()` trả `FLY_ENOSYS`. Mạng NTC BQ25070 đã chốt
   **R1=20 kΩ (LDO→TS), R2=8,25 kΩ (TS→GND)**, NTC 10 kΩ B3950; cần driver
   1-Wire cho DS18B20 trước khi trả số đo. Lõi ghi `0x80` +
   `FAULT_CODE=SENSOR_STALE` cho tới lúc đó.
7. **Ghi EEPROM**: `nvm_write()` trả `FLY_ENOSYS`; cần mở khóa `PEKEYR`, xóa
   trang, ghi, chờ `EOP`. Chưa làm vì chưa đối chiếu RM.
8. **ISR I2C**: khung mới cấu hình, chưa có ISR gọi `fly_i2c_read/write`.
9. **Giờ RTC**: `epoch_s()` đọc lịch BCD và đổi sang Unix; chưa có phần đặt giờ
   từ SoC và chưa xử lý `RTC_LOST` (bit 5 của `SYS_FLAGS`).
10. **Nguồn clock RTC/WUCKSEL**: mã đã chọn LSI, đặt PRER và WUCKSEL; đây là
    phần **chưa chạy trên target**. Phải scope chân WKUP hoặc đo thời gian ngủ
    thực: nếu thức sớm ~16 lần, kiểm lại WUCKSEL/PRER. Giới hạn ngủ: 28 s ở
    chế độ ms, 65535 s ở chế độ 1 Hz.

## 3. Cách build khi có SDK

```sh
# ví dụ, chưa chạy lần nào
arm-none-eabi-gcc -std=c99 -mcpu=cortex-m0plus -mthumb \
  -DFLYTEX_TARGET_STM32L0 \
  -Ifirmware/mcu/include \
  firmware/mcu/src/*.c firmware/mcu/hal/stm32l0/port_stm32l0.c \
  -o build/flytex-mcu.elf
```

Build host (`tests/build.py`) **không** dùng lệnh trên và không cần toolchain ARM.

## 4. Bảng chân tạm

| Tín hiệu | Chân tạm | Ghi chú |
|---|---|---|
| PIR | PA0 | EXTI, đánh thức |
| VBUS | PA1 | EXTI, đánh thức |
| MODEM_STATUS | PA2 | EXTI, đánh thức |
| SOC_READY | PA3 | vào |
| MODEM_RI | PA4 | EXTI, phải chốt cạnh trong ISR |
| SOC_PWR | PB0 | ra, mức tích cực xem `config.h` |
| MODEM_PWR | PB1 | ra |
| IRQ | PB2 | ra, open-drain, mức thấp là có sự kiện |
| IR_LED | PB3 | ra |
| CHG_CTRL | PB4 | ra; 11 xung lúc boot = 935 mA, giữ cao >2 ms để ngắt sạc |
| MODEM_RESET | PB5 | ra, xung |
| MODEM_PWRKEY | PB6 | ra, xung |

Bảng này **không phải pinout đã chốt**; đổi theo schematic, giữ nguyên thứ tự
theo `enum fly_pin`.
