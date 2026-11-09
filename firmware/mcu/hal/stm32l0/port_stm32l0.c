/*
 * port_stm32l0.c — KHUNG port STM32L0 cho MCU giám sát.
 *
 * ==========================================================================
 *  CHƯA BUILD, CHƯA KIỂM CHỨNG TRÊN PHẦN CỨNG.
 *  Không có SDK, không có board PWR ở giai đoạn hiện tại (docs/14 §7).
 *  Mọi địa chỉ/bit dưới đây là bản nháp đọc từ reference manual, phải đối
 *  chiếu lại với RM của đúng mã chip và với schematic trước khi dùng.
 *  Chỗ chưa chắc chắn đánh dấu [CHƯA XÁC MINH].
 * ==========================================================================
 *
 * File này KHÔNG nằm trong build host: tests/build.py chỉ biên dịch các file
 * .c trong src/ và hal/host/ (kèm sim/ffi.c), và toàn bộ nội dung ở đây bị
 * bọc trong `#if defined(FLYTEX_TARGET_STM32L0)`. Muốn build cho target phải
 * định nghĩa macro đó và thêm file này vào danh sách nguồn.
 *
 * Những gì đã có trong khung:
 *   - bản đồ thanh ghi tối thiểu (GPIO, RCC, PWR, EXTI, IWDG, ADC, I2C1, RTC);
 *   - vào STOP mode thật, hẹn giờ bằng RTC wakeup timer, đọc lại nguồn thức;
 *   - ADC hiệu chuẩn bằng VREFINT (đọc hằng số hiệu chuẩn trong system memory);
 *   - IWDG, EEPROM dữ liệu, nguyên nhân reset, giờ RTC;
 *   - I2C1 slave có WUPEN (đánh thức bằng địa chỉ) — phần chưa kiểm chứng nhất.
 *
 * Những gì CỐ TÌNH chưa có (trả lỗi rõ, không giả vờ):
 *   - đọc NTC và DS18B20: temp_c() trả FLY_ENOSYS. Cần bảng tra NTC và driver
 *     1-Wire trước khi trả số đo;
 *   - bảng chân thật: hàm pin_map() là chỗ giữ chỗ, phải lấy từ schematic;
 *   - ghi EEPROM (nvm_write trả FLY_ENOSYS) và ISR I2C.
 */
#include <stdint.h>

#include "flytex/hal.h"
#include "flytex/regs_gen.h"

#if defined(FLYTEX_TARGET_STM32L0)

/* ---------------------------------------------------------------------- */
/* Bản đồ thanh ghi tối thiểu (không phụ thuộc SDK)                        */
/* ---------------------------------------------------------------------- */

typedef struct {
    volatile uint32_t MODER;
    volatile uint32_t OTYPER;
    volatile uint32_t OSPEEDR;
    volatile uint32_t PUPDR;
    volatile uint32_t IDR;
    volatile uint32_t ODR;
    volatile uint32_t BSRR;
    volatile uint32_t LCKR;
    volatile uint32_t AFR[2];
    volatile uint32_t BRR;
} fly_gpio_t;

typedef struct {
    volatile uint32_t CR;
    volatile uint32_t ICSCR;
    volatile uint32_t CFGR;
    volatile uint32_t CIER;
    volatile uint32_t CIFR;
    volatile uint32_t CICR;
    volatile uint32_t IOPRSTR;
    volatile uint32_t AHBRSTR;
    volatile uint32_t APB2RSTR;
    volatile uint32_t APB1RSTR;
    volatile uint32_t IOPENR;
    volatile uint32_t AHBENR;
    volatile uint32_t APB2ENR;
    volatile uint32_t APB1ENR;
    volatile uint32_t CRRCR;
    volatile uint32_t CCIPR;
    volatile uint32_t CSR;
} fly_rcc_t;

/* PWR trên STM32L0 chỉ có CR và CSR [CHƯA XÁC MINH — đối chiếu RM]. */
typedef struct {
    volatile uint32_t CR;
    volatile uint32_t CSR;
} fly_pwr_t;

typedef struct {
    volatile uint32_t IMR;
    volatile uint32_t EMR;
    volatile uint32_t RTSR;
    volatile uint32_t FTSR;
    volatile uint32_t SWIER;
    volatile uint32_t PR;
} fly_exti_t;

typedef struct {
    volatile uint32_t KR;
    volatile uint32_t PR;
    volatile uint32_t RLR;
    volatile uint32_t SR;
    volatile uint32_t WINR;
} fly_iwdg_t;

typedef struct {
    volatile uint32_t ISR;
    volatile uint32_t IER;
    volatile uint32_t CR;
    volatile uint32_t CFGR1;
    volatile uint32_t CFGR2;
    volatile uint32_t SMPR;
    volatile uint32_t TR;
    volatile uint32_t CHSELR;
    volatile uint32_t DR;
} fly_adc_t;

typedef struct {
    volatile uint32_t CCR;
} fly_adc_common_t;

typedef struct {
    volatile uint32_t CR1;
    volatile uint32_t CR2;
    volatile uint32_t OAR1;
    volatile uint32_t OAR2;
    volatile uint32_t TIMINGR;
    volatile uint32_t TIMEOUTR;
    volatile uint32_t ISR;
    volatile uint32_t ICR;
    volatile uint32_t PECR;
    volatile uint32_t RXDR;
    volatile uint32_t TXDR;
} fly_i2c_t;

typedef struct {
    volatile uint32_t TR;
    volatile uint32_t DR;
    volatile uint32_t CR;
    volatile uint32_t ISR;
    volatile uint32_t PRER;
    volatile uint32_t WUTR;
    volatile uint32_t ALRMAR;
    volatile uint32_t ALRMBR;
    volatile uint32_t WPR;
    volatile uint32_t SSR;
    volatile uint32_t SHIFTR;
    volatile uint32_t TSTR;
    volatile uint32_t TSDR;
    volatile uint32_t TSSSR;
    volatile uint32_t CALR;
    volatile uint32_t TAMPCR;
    volatile uint32_t ALRMASSR;
    volatile uint32_t ALRMBSSR;
    volatile uint32_t OR;
} fly_rtc_t;

#define FLY_GPIOA ((fly_gpio_t *)0x50000000u)
#define FLY_GPIOB ((fly_gpio_t *)0x50000400u)
#define FLY_GPIOC ((fly_gpio_t *)0x50000800u)
#define FLY_RCC ((fly_rcc_t *)0x40021000u)
#define FLY_PWR ((fly_pwr_t *)0x40007000u)
#define FLY_EXTI ((fly_exti_t *)0x40010400u)
#define FLY_IWDG ((fly_iwdg_t *)0x40003000u)
#define FLY_ADC1 ((fly_adc_t *)0x40012400u)
#define FLY_ADC_COMMON ((fly_adc_common_t *)0x40012708u)
#define FLY_I2C1 ((fly_i2c_t *)0x40005400u)
#define FLY_RTC ((fly_rtc_t *)0x40002800u)
#define FLY_EEPROM ((volatile uint8_t *)0x08080000u)
#define FLY_SCB_SCR (*(volatile uint32_t *)0xE000ED10u) /* SLEEPDEEP */

/* RCC_CSR: cờ nguồn reset [CHƯA XÁC MINH — đối chiếu RM đúng mã chip]. */
#define FLY_RCC_CSR_RMVF (1uL << 24)
#define FLY_RCC_CSR_OBLRSTF (1uL << 25)
#define FLY_RCC_CSR_PINRSTF (1uL << 26)
#define FLY_RCC_CSR_PORRSTF (1uL << 27)
#define FLY_RCC_CSR_SFTRSTF (1uL << 28)
#define FLY_RCC_CSR_WWDGRSTF (1uL << 29)
#define FLY_RCC_CSR_IWDGRSTF (1uL << 30)
#define FLY_RCC_CSR_LPWRRSTF (1uL << 31)
#define FLY_SCB_SCR_SLEEPDEEP (1uL << 2)

/* PWR_CR [CHƯA XÁC MINH]. */
#define FLY_PWR_CR_LPSDSR (1uL << 0)
#define FLY_PWR_CR_PDDS (1uL << 1)
#define FLY_PWR_CR_CWUF (1uL << 2)
#define FLY_PWR_CR_CSBF (1uL << 3)

/* RTC_CR / RTC_ISR. */
#define FLY_RTC_CR_WUTE (1uL << 10)
#define FLY_RTC_ISR_WUTWF (1uL << 2)
#define FLY_RTC_ISR_WUTF (1uL << 10)
#define FLY_RTC_WPR_KEY1 0xCAu
#define FLY_RTC_WPR_KEY2 0x53u

/* EXTI: RTC wakeup timer là line 20 [CHƯA XÁC MINH]. */
#define FLY_EXTI_LINE_RTC_WUT (1uL << 20)

/* LSI danh định 37 kHz trên STM32L0 [CHƯA XÁC MINH — đo lại]. */
#define FLY_LSI_HZ 37000u

/* VREFINT_CAL: 16 bit trong system memory, đo ở VDDA = 3,0 V. */
#define FLY_VREFINT_CAL_ADDR ((const volatile uint16_t *)0x1FF80078u)
#define FLY_VREFINT_CAL_MV 3000u
#define FLY_ADC_FULL_SCALE 4095u
#define FLY_ADC_CH_VREFINT 17u

#if defined(__arm__)
#define FLY_WFI() __asm volatile("wfi")
#define FLY_DSB() __asm volatile("dsb" ::: "memory")
#else
/* Chỉ để kiểm tra cú pháp trên máy host; không chạy được. */
#define FLY_WFI() ((void)0)
#define FLY_DSB() ((void)0)
#endif

/* ---------------------------------------------------------------------- */
/* Bảng chân — CHỖ GIỮ CHỖ, phải lấy từ schematic PWR                     */
/* ---------------------------------------------------------------------- */

/*
 * [CHƯA XÁC MINH] Ánh xạ tạm, KHÔNG phải pinout đã chốt. Sửa theo schematic;
 * giữ nguyên thứ tự theo enum fly_pin.
 */
static int pin_map(int pin, fly_gpio_t **port, uint32_t *index)
{
    switch (pin) {
    case FLY_PIN_PIR:
        *port = FLY_GPIOA;
        *index = 0u;
        return 1;
    case FLY_PIN_VBUS:
        *port = FLY_GPIOA;
        *index = 1u;
        return 1;
    case FLY_PIN_MODEM_STATUS:
        *port = FLY_GPIOA;
        *index = 2u;
        return 1;
    case FLY_PIN_SOC_READY:
        *port = FLY_GPIOA;
        *index = 3u;
        return 1;
    case FLY_PIN_MODEM_RI:
        *port = FLY_GPIOA;
        *index = 4u;
        return 1;
    case FLY_PIN_SOC_PWR:
        *port = FLY_GPIOB;
        *index = 0u;
        return 1;
    case FLY_PIN_MODEM_PWR:
        *port = FLY_GPIOB;
        *index = 1u;
        return 1;
    case FLY_PIN_IRQ:
        *port = FLY_GPIOB;
        *index = 2u;
        return 1;
    case FLY_PIN_IR_LED:
        *port = FLY_GPIOB;
        *index = 3u;
        return 1;
    case FLY_PIN_CHG_INHIBIT:
        *port = FLY_GPIOB;
        *index = 4u;
        return 1;
    case FLY_PIN_MODEM_RESET:
        *port = FLY_GPIOB;
        *index = 5u;
        return 1;
    case FLY_PIN_MODEM_PWRKEY:
        *port = FLY_GPIOB;
        *index = 6u;
        return 1;
    default:
        *port = 0;
        *index = 0u;
        return 0;
    }
}

/* Cấu hình một chân: output = 1 thì MODER = 01, ngược lại 00 (vào). */
static void gpio_config(int pin, int output)
{
    fly_gpio_t *port = 0;
    uint32_t index = 0u;
    uint32_t shift;

    if (!pin_map(pin, &port, &index)) {
        return;
    }
    shift = 2uL * index;
    port->MODER = (port->MODER & ~(3uL << shift)) | ((output ? 1uL : 0uL) << shift);
}

void fly_port_gpio_init(void)
{
    int pin;

    /* Bật clock GPIOA/GPIOB [CHƯA XÁC MINH — tên bit IOPENR]. */
    FLY_RCC->IOPENR |= (1uL << 0) | (1uL << 1);

    for (pin = 0; pin < (int)FLY_PIN_COUNT; pin++) {
        gpio_config(pin, fly_pin_is_output(pin));
    }
}

/* ---------------------------------------------------------------------- */
/* HAL: thời gian                                                          */
/* ---------------------------------------------------------------------- */

static uint32_t rtc_bcd(uint32_t value)
{
    return ((value >> 4) * 10u) + (value & 0x0Fu);
}

/* Số ngày kể từ 1970-01-01, thuật toán days_from_civil của Hinnant. */
static int32_t days_from_civil(int32_t year, int32_t month, int32_t day)
{
    int32_t era;
    int32_t y;
    uint32_t yoe;
    uint32_t doy;
    uint32_t doe;

    y = year - (month <= 2 ? 1 : 0);
    era = (y >= 0 ? y : y - 399) / 400;
    yoe = (uint32_t)(y - era * 400);
    doy = (uint32_t)((153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1);
    doe = yoe * 365u + yoe / 4u - yoe / 100u + doy;
    return era * 146097 + (int32_t)doe - 719468;
}

static uint64_t port_epoch_s(void *ctx)
{
    uint32_t tr;
    uint32_t dr;
    int32_t days;

    (void)ctx;
    tr = FLY_RTC->TR;
    dr = FLY_RTC->DR;
    if ((tr & (1uL << 6)) != 0u) {
        return 0u; /* RTC đang cập nhật, chưa đọc được [CHƯA XÁC MINH] */
    }
    days = days_from_civil(2000 + (int32_t)rtc_bcd((dr >> 16) & 0xFFu),
                           (int32_t)rtc_bcd((dr >> 8) & 0x1Fu),
                           (int32_t)rtc_bcd(dr & 0x3Fu));
    return (uint64_t)days * 86400ull + (uint64_t)rtc_bcd((tr >> 16) & 0x7Fu) * 3600ull +
           (uint64_t)rtc_bcd((tr >> 8) & 0x7Fu) * 60ull + (uint64_t)rtc_bcd(tr & 0x7Fu);
}

static uint32_t port_millis(void *ctx)
{
    uint32_t prer;
    uint32_t ssr;
    uint32_t sub;
    uint32_t ms;

    prer = FLY_RTC->PRER & 0x7FFFu; /* PREDIV_S */
    ssr = FLY_RTC->SSR & 0x7FFFu;
    if (prer == 0u) {
        return 0u;
    }
    sub = ((prer + 1u) - ssr) % (prer + 1u);
    ms = (sub * 1000u) / (prer + 1u);
    return (uint32_t)((port_epoch_s(ctx) * 1000ull) + (uint64_t)ms);
}

/* ---------------------------------------------------------------------- */
/* HAL: STOP mode + RTC wakeup                                             */
/* ---------------------------------------------------------------------- */

static void rtc_unlock(void)
{
    FLY_RTC->WPR = FLY_RTC_WPR_KEY1;
    FLY_RTC->WPR = FLY_RTC_WPR_KEY2;
}

static void rtc_lock(void)
{
    FLY_RTC->WPR = 0xFFu;
}

static void rtc_wakeup_arm(uint32_t ticks)
{
    uint32_t guard = 0u;

    rtc_unlock();
    FLY_RTC->CR &= ~FLY_RTC_CR_WUTE;
    while ((FLY_RTC->ISR & FLY_RTC_ISR_WUTWF) == 0u && guard < 100000u) {
        guard++;
    }
    FLY_RTC->WUTR = ticks & 0xFFFFu;
    FLY_RTC->ISR = ~FLY_RTC_ISR_WUTF; /* ghi 0 để xóa cờ */
    FLY_RTC->CR |= FLY_RTC_CR_WUTE;
    rtc_lock();
    FLY_EXTI->IMR |= FLY_EXTI_LINE_RTC_WUT;
}

static void rtc_wakeup_disarm(void)
{
    rtc_unlock();
    FLY_RTC->CR &= ~FLY_RTC_CR_WUTE;
    rtc_lock();
}

static uint32_t port_enter_stop(void *ctx, uint32_t max_ms)
{
    uint32_t mask = 0u;
    uint32_t wake;

    (void)ctx;
    if (max_ms > 0u && max_ms != UINT32_MAX) {
        uint32_t ticks = (uint32_t)(((uint64_t)max_ms * FLY_LSI_HZ) / 1000ull);
        if (ticks > 0xFFFFu) {
            ticks = 0xFFFFu;
        }
        rtc_wakeup_arm(ticks);
    } else {
        rtc_wakeup_disarm();
    }

    /* Xóa cờ thức cũ, chọn STOP (không phải Standby). */
    FLY_PWR->CR |= FLY_PWR_CR_CWUF | FLY_PWR_CR_CSBF;
    FLY_PWR->CR &= ~FLY_PWR_CR_PDDS;
    FLY_PWR->CR |= FLY_PWR_CR_LPSDSR;

    FLY_DSB();
    FLY_SCB_SCR |= FLY_SCB_SCR_SLEEPDEEP;
    FLY_WFI();
    FLY_SCB_SCR &= ~FLY_SCB_SCR_SLEEPDEEP;

    /*
     * Đọc nguồn đánh thức. WUF1..WUF6 là các chân WKUP của PWR, không phải
     * mọi chân EXTI [CHƯA XÁC MINH]; muốn biết PIR/VBUS/RI đánh thức thì phải
     * đọc EXTI->PR sau khi đã cấu hình các line tương ứng.
     */
    wake = FLY_PWR->CSR;
    if ((wake & 0x0100u) != 0u) { /* WUF1 [CHƯA XÁC MINH] */
        mask |= FLY_WAKE_PIR;
    }
    if ((FLY_EXTI->PR & (1uL << 1)) != 0u) {
        mask |= FLY_WAKE_VBUS;
    }
    if ((FLY_EXTI->PR & (1uL << 2)) != 0u) {
        mask |= FLY_WAKE_MODEM_STATUS;
    }
    if ((FLY_EXTI->PR & (1uL << 4)) != 0u) {
        mask |= FLY_WAKE_OTHER;
    }
    if ((FLY_EXTI->PR & FLY_EXTI_LINE_RTC_WUT) != 0u) {
        mask |= FLY_WAKE_RTC;
    }
    FLY_EXTI->PR = 0xFFFFFFFFu; /* ghi 1 để xóa */
    FLY_PWR->CR |= FLY_PWR_CR_CWUF | FLY_PWR_CR_CSBF;
    return mask;
}

/* ---------------------------------------------------------------------- */
/* HAL: GPIO                                                               */
/* ---------------------------------------------------------------------- */

static int port_gpio_read(void *ctx, int pin)
{
    fly_gpio_t *port = 0;
    uint32_t index = 0u;

    (void)ctx;
    if (!pin_map(pin, &port, &index)) {
        return 0;
    }
    return (port->IDR & (1uL << index)) ? 1 : 0;
}

static void port_gpio_write(void *ctx, int pin, int level)
{
    fly_gpio_t *port = 0;
    uint32_t index = 0u;
    uint32_t bit;

    (void)ctx;
    if (!pin_map(pin, &port, &index)) {
        return;
    }
    bit = 1uL << index;
    if (level) {
        port->BSRR = bit;
    } else {
        port->BRR = bit;
    }
}

/* ---------------------------------------------------------------------- */
/* HAL: ADC + hiệu chuẩn VREFINT                                           */
/* ---------------------------------------------------------------------- */

static uint32_t adc_read_raw(uint32_t channel)
{
    uint32_t guard = 0u;

    FLY_ADC1->CHSELR = 1uL << channel;
    FLY_ADC1->CR |= (1uL << 2); /* ADSTART */
    while ((FLY_ADC1->ISR & (1uL << 2)) == 0u && guard < 100000u) { /* EOC */
        guard++;
    }
    return FLY_ADC1->DR & 0x0FFFu;
}

/* VDDA thật, mV, suy ra từ kênh VREFINT và hằng số hiệu chuẩn. */
static uint32_t adc_vdda_mv(void)
{
    uint32_t cal = (uint32_t)(*FLY_VREFINT_CAL_ADDR);
    uint32_t raw = adc_read_raw(FLY_ADC_CH_VREFINT);

    if (cal == 0u || cal == 0xFFFFu || raw == 0u) {
        return 0u;
    }
    return (FLY_VREFINT_CAL_MV * cal) / raw;
}

static int port_adc_mv(void *ctx, int ch, uint32_t *mv)
{
    uint32_t vdda;
    uint32_t raw;

    (void)ctx;
    if (!mv) {
        return FLY_EINVAL;
    }
    if (ch != FLY_ADC_VBAT) {
        return FLY_EINVAL;
    }

    /* ADC phải đã được bật và hiệu chuẩn trong fly_port_init(). */
    vdda = adc_vdda_mv();
    if (vdda == 0u) {
        return FLY_EIO;
    }
    raw = adc_read_raw(1u); /* kênh 1: chân chia áp VBAT [CHƯA XÁC MINH] */
    *mv = (raw * vdda) / FLY_ADC_FULL_SCALE;
    return FLY_OK;
}

/* ---------------------------------------------------------------------- */
/* HAL: nhiệt độ (chưa hiện thực)                                          */
/* ---------------------------------------------------------------------- */

static int port_temp_c(void *ctx, int sensor, int8_t *c)
{
    (void)ctx;
    (void)sensor;
    (void)c;
    /*
     * NTC trên pack: cần bảng tra điện trở–nhiệt độ và điện trở kéo thật.
     * DS18B20: cần driver 1-Wire có định thời micro giây.
     * Chưa làm thì trả FLY_ENOSYS để lõi ghi 0x80 + SENSOR_STALE, tuyệt đối
     * không trả một giá trị nhiệt độ giả.
     */
    return FLY_ENOSYS;
}

/* ---------------------------------------------------------------------- */
/* HAL: NVM (EEPROM dữ liệu)                                              */
/* ---------------------------------------------------------------------- */

static int port_nvm_read(void *ctx, uint32_t off, void *buf, uint32_t len)
{
    uint8_t *out = (uint8_t *)buf;
    uint32_t i;

    (void)ctx;
    if (!buf || off > 0x1000u || len > (0x1000u - off)) {
        return FLY_EINVAL;
    }
    for (i = 0; i < len; i++) {
        out[i] = FLY_EEPROM[off + i];
    }
    return FLY_OK;
}

static int port_nvm_write(void *ctx, uint32_t off, const void *buf, uint32_t len)
{
    (void)ctx;
    if (!buf || off > 0x1000u || len > (0x1000u - off)) {
        return FLY_EINVAL;
    }
    /*
     * Ghi EEPROM cần mở khóa FLASH (PEKEYR) và chờ EOP; chưa viết vì chưa
     * đối chiếu RM. Trả lỗi rõ thay vì giả vờ ghi thành công.
     */
    return FLY_ENOSYS;
}

/* ---------------------------------------------------------------------- */
/* HAL: watchdog, reset, I2C                                               */
/* ---------------------------------------------------------------------- */

static void port_wdg_kick(void *ctx)
{
    (void)ctx;
    FLY_IWDG->KR = 0xAAAAu; /* reload */
}

static uint8_t port_reset_cause(void *ctx)
{
    uint32_t csr;
    uint8_t flags = 0u;

    (void)ctx;
    csr = FLY_RCC->CSR;
    if ((csr & FLY_RCC_CSR_IWDGRSTF) != 0u) {
        flags = (uint8_t)(flags | FLY_SYS_FLAGS_WDT_RESET);
    }
    if ((csr & (FLY_RCC_CSR_PORRSTF | FLY_RCC_CSR_LPWRRSTF)) != 0u) {
        flags = (uint8_t)(flags | FLY_SYS_FLAGS_POR_BOR);
    }
    if ((csr & FLY_RCC_CSR_PINRSTF) != 0u) {
        flags = (uint8_t)(flags | FLY_SYS_FLAGS_PIN_RESET);
    }
    if ((csr & (FLY_RCC_CSR_SFTRSTF | FLY_RCC_CSR_OBLRSTF)) != 0u) {
        flags = (uint8_t)(flags | FLY_SYS_FLAGS_SOFTWARE);
    }
    FLY_RCC->CSR |= FLY_RCC_CSR_RMVF; /* xóa cờ để lần sau đọc sạch */
    return flags;
}

/*
 * I2C1 slave. Địa chỉ 7 bit lấy từ flytex/regs_gen.h (FLY_I2C_ADDR).
 * WUPEN cho phép đánh thức khỏi STOP khi master gọi đúng địa chỉ; đây là
 * hành vi [CHƯA XÁC MINH] trong reference manual (docs/14 §3.1, docs/04 §2.2).
 * Cần thêm ISR đọc/ghi RXDR/TXDR gọi fly_i2c_read/fly_i2c_write.
 */
void fly_port_i2c_slave_init(void)
{
    FLY_RCC->APB1ENR |= (1uL << 21); /* I2C1EN [CHƯA XÁC MINH] */
    FLY_I2C1->CR1 = 0u;
    FLY_I2C1->OAR1 = (uint32_t)(((uint32_t)FLY_I2C_ADDR << 1) | 0x4000u); /* OA1EN */
    FLY_I2C1->CR1 = (1uL << 0) |  /* PE */
                    (1uL << 18);  /* WUPEN [CHƯA XÁC MINH bit] */
}

/* ---------------------------------------------------------------------- */
/* Khởi tạo chung                                                          */
/* ---------------------------------------------------------------------- */

void fly_port_init(fly_hal_t *hal)
{
    uint32_t guard = 0u;

    if (!hal) {
        return;
    }

    /* RTC clock từ LSE nếu có, nguồn khác LSI [CHƯA XÁC MINH]. */
    FLY_RCC->CSR |= (1uL << 16); /* RTCEN */
    while ((FLY_RCC->CSR & (1uL << 17)) == 0u && guard < 1000000u) {
        guard++;
    }

    /* ADC: bật clock, bật ADC, hiệu chuẩn. */
    FLY_RCC->APB2ENR |= (1uL << 9); /* ADC1EN [CHƯA XÁC MINH] */
    FLY_ADC1->CR |= (1uL << 0);     /* ADEN */
    FLY_ADC1->CR |= (1uL << 31);    /* ADCAL */
    guard = 0u;
    while ((FLY_ADC1->CR & (1uL << 31)) != 0u && guard < 1000000u) {
        guard++;
    }
    FLY_ADC_COMMON->CCR |= (1uL << 22); /* VREFEN [CHƯA XÁC MINH] */

    /* IWDG: LSI ~37 kHz, chia 256, reload 4095 → khoảng 28 s. */
    FLY_IWDG->KR = 0xCCCCu; /* start */
    FLY_IWDG->KR = 0x5555u; /* cho phép ghi PR/RLR */
    FLY_IWDG->PR = 0x06u;   /* /256 [CHƯA XÁC MINH] */
    FLY_IWDG->RLR = 0x0FFFu;
    FLY_IWDG->KR = 0xAAAAu;

    fly_port_gpio_init();
    fly_port_i2c_slave_init();

    hal->millis = port_millis;
    hal->enter_stop = port_enter_stop;
    hal->gpio_read = port_gpio_read;
    hal->gpio_write = port_gpio_write;
    hal->adc_mv = port_adc_mv;
    hal->temp_c = port_temp_c;
    hal->nvm_read = port_nvm_read;
    hal->nvm_write = port_nvm_write;
    hal->wdg_kick = port_wdg_kick;
    hal->epoch_s = port_epoch_s;
    hal->reset_cause = port_reset_cause;
}

#else

/* Bản dịch rỗng khi không nhắm STM32L0: không lọt vào build host. */
typedef int fly_port_stm32l0_not_selected;

#endif /* FLYTEX_TARGET_STM32L0 */
