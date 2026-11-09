/*
 * hal.h — hợp đồng HAL của lõi MCU giám sát.
 *
 * Quy ước về tham số `void *ctx`: lõi chỉ nhận đúng một tham số ở fly_init()
 * là bảng fly_hal_t, nên mỗi hàm HAL nhận chính con trỏ bảng HAL đó. HAL hiện
 * thực đặt fly_hal_t là thành viên ĐẦU TIÊN của struct trạng thái riêng rồi
 * lấy lại con trỏ bằng một phép ép kiểu (xem hal/host/hal_host.c và
 * hal/stm32l0/port_stm32l0.c). Nhờ vậy không cần biến toàn cục.
 *
 * Mọi hàm trả FLY_OK (0) khi thành công, số âm khi lỗi.
 */
#ifndef FLYTEX_HAL_H
#define FLYTEX_HAL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Mã lỗi dùng chung. NACK trên bus I2C trả FLY_EIO. */
#define FLY_OK 0
#define FLY_ENOSYS (-2)
#define FLY_EINVAL (-3)
#define FLY_EIO (-4)

/*
 * Chân logic. Số 4..7 được dành chỗ từ đầu để không phải đánh số lại khi
 * thêm chân; hiện FLY_PIN_MODEM_RI dùng số 4, còn 5..7 để trống.
 *
 * FLY_PIN_MODEM_RI và hai chân xung modem được thêm so với bản liệt kê ban
 * đầu: RI là tín hiệu của modem (J_B2B chân 21, docs/15 §4.2) dùng để đánh
 * thức khi SoC tắt bằng SMS; MODEM_RESET/MODEM_PWRKEY cần chân để phát xung.
 * Xem README.md, mục "Khác biệt so với đặc tả".
 */
enum fly_pin {
    FLY_PIN_PIR = 0,
    FLY_PIN_VBUS = 1,
    FLY_PIN_MODEM_STATUS = 2,
    FLY_PIN_SOC_READY = 3,
    FLY_PIN_MODEM_RI = 4,

    FLY_PIN_SOC_PWR = 8,
    FLY_PIN_MODEM_PWR = 9,
    FLY_PIN_IRQ = 10,
    FLY_PIN_IR_LED = 11,
    FLY_PIN_CHG_INHIBIT = 12,
    FLY_PIN_MODEM_RESET = 13,
    FLY_PIN_MODEM_PWRKEY = 14,

    FLY_PIN_COUNT = 15
};

/* Bit của bitmask nguồn đánh thức do enter_stop() trả về. */
#define FLY_WAKE_PIR (1u << 0)
#define FLY_WAKE_VBUS (1u << 1)
#define FLY_WAKE_MODEM_STATUS (1u << 2)
#define FLY_WAKE_RTC (1u << 3)
#define FLY_WAKE_I2C (1u << 4)
#define FLY_WAKE_OTHER (1u << 5)

/* Kênh ADC. */
#define FLY_ADC_VBAT 0
#define FLY_ADC_CHANNELS 2

/* Cảm biến nhiệt. */
#define FLY_TEMP_BATT 0
#define FLY_TEMP_AMB 1
#define FLY_TEMP_SENSORS 2

/* Giá trị int8 nghĩa là "không có cảm biến / không đọc được". */
#define FLY_TEMP_INVALID (-128)

typedef struct {
    /*
     * Đồng hồ đơn điệu, mili giây, tràn sau 49 ngày. Lõi luôn so sánh bằng
     * hiệu (uint32_t) nên chịu được tràn.
     */
    uint32_t (*millis)(void *ctx);

    /*
     * Vào STOP mode thật, ngủ tối đa max_ms, trả bitmask FLY_WAKE_*.
     * max_ms = 0 nghĩa là không hẹn giờ (chỉ thức bởi nguồn ngoài).
     */
    uint32_t (*enter_stop)(void *ctx, uint32_t max_ms);

    /* Đọc mức chân, id theo enum fly_pin. Trả 0 hoặc 1. */
    int (*gpio_read)(void *ctx, int pin);

    /* Đặt mức chân ra. */
    void (*gpio_write)(void *ctx, int pin, int level);

    /* Delay ngắn cho giao diện xung (CTRL của sạc). Có thể là no-op trên host. */
    void (*delay_us)(void *ctx, uint32_t us);

    /*
     * Đọc ADC đã hiệu chuẩn: *mv là mili vôn TẠI CHÂN ADC, tức sau mạch chia.
     * Lõi tự nhân hệ số chia trong config.h (FLY_BATT_DIV_NUM/DEN).
     */
    int (*adc_mv)(void *ctx, int ch, uint32_t *mv);

    /* Nhiệt độ theo cảm biến; FLY_ENOSYS nếu phần cứng không có cảm biến. */
    int (*temp_c)(void *ctx, int sensor, int8_t *c);

    /* Bộ nhớ cấu hình bền qua mất điện. */
    int (*nvm_read)(void *ctx, uint32_t off, void *buf, uint32_t len);
    int (*nvm_write)(void *ctx, uint32_t off, const void *buf, uint32_t len);

    /* Cho watchdog ăn. Chỉ gọi từ fly_step(), không gọi trong ngắt. */
    void (*wdg_kick)(void *ctx);

    /* Giờ thực, nếu có RTC. Trả 0 nếu chưa có giờ. */
    uint64_t (*epoch_s)(void *ctx);

    /* Nguyên nhân khởi động lại, cùng bố cục bit với SYS_FLAGS. */
    uint8_t (*reset_cause)(void *ctx);
} fly_hal_t;

/* Chân nào là đầu vào / đầu ra. Dùng chung cho HAL host và FFI. */
static inline int fly_pin_is_input(int pin)
{
    return pin >= FLY_PIN_PIR && pin <= FLY_PIN_MODEM_RI;
}

static inline int fly_pin_is_output(int pin)
{
    return pin >= FLY_PIN_SOC_PWR && pin < FLY_PIN_COUNT;
}

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_HAL_H */
