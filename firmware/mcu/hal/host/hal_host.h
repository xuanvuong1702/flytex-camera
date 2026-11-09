/*
 * hal_host.h — HAL giả chạy trên máy tính, dùng cho kiểm thử và cho thư viện
 * mô phỏng (sim/ffi.c).
 *
 * Thời gian là biến mô phỏng: enter_stop KHÔNG ngủ thật, nó cộng thời gian
 * mô phỏng (tối đa max_ms) và trả về bitmask nguồn đánh thức đang ở mức tích
 * cực. Không có sleep, không có đồng hồ hệ thống.
 *
 * Quy ước con trỏ: hàm HAL nhận `void *ctx` = &h->hal. Vì `hal` là thành viên
 * ĐẦU TIÊN của hal_host_t, ép kiểu ngược lại là hợp lệ; đừng đổi thứ tự field.
 */
#ifndef FLYTEX_HAL_HOST_H
#define FLYTEX_HAL_HOST_H

#include <stdint.h>

#include "flytex/hal.h"

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

#define FLY_HOST_NVM_SIZE 256u

typedef struct {
    uint32_t stop_entries;
    uint32_t stop_ms;
    uint32_t wdg_kicks;
    uint32_t i2c_nacks;
    uint32_t steps;
} hal_host_stats_t;

typedef struct hal_host {
    fly_hal_t hal; /* PHẢI là thành viên đầu tiên (xem quy ước trên) */

    uint32_t now_ms;
    uint64_t epoch_base_s;
    uint8_t reset_flags;

    int input_level[FLY_PIN_COUNT];
    int output_level[FLY_PIN_COUNT];
    uint32_t adc_mv[FLY_ADC_CHANNELS];
    int16_t temp_c[FLY_TEMP_SENSORS];

    uint8_t nvm[FLY_HOST_NVM_SIZE];
    hal_host_stats_t stats;
} hal_host_t;

/*
 * Khởi tạo: thời gian 0, NVM trắng (0xFF), ADC kênh pin = 1650 mV (3,3 V sau
 * chia 1:2, giá trị bench), cảm biến nhiệt = không có, stats = 0.
 */
void hal_host_init(hal_host_t *h);

/* Xóa toàn bộ trạng thái, kể cả NVM và stats. */
void hal_host_reset(hal_host_t *h);

/* Chỉ xóa bộ đếm thống kê. */
void hal_host_clear_stats(hal_host_t *h);

/* Đặt mức chân vào (chỉ chân input). Trả FLY_OK hoặc FLY_EINVAL. */
int hal_host_set_input(hal_host_t *h, int pin, int level);

/* Mức chân vào/ra; -1 nếu sai hướng hoặc sai số chân. */
int hal_host_get_input(const hal_host_t *h, int pin);
int hal_host_get_output(const hal_host_t *h, int pin);

/* Đặt giá trị ADC (mV tại chân) và nhiệt độ (int8, -128 = không có). */
int hal_host_set_adc_mv(hal_host_t *h, int ch, uint32_t mv);
int hal_host_set_temp_c(hal_host_t *h, int sensor, int celsius);

/* Đặt bit nguyên nhân khởi động lại (cùng bố cục SYS_FLAGS). */
void hal_host_set_reset_cause(hal_host_t *h, uint8_t flags);

const hal_host_stats_t *hal_host_stats(const hal_host_t *h);

/*
 * Bộ đếm steps lấy từ lõi (fly_ctx_t.steps) vì chỉ lõi biết mình chạy bao
 * nhiêu bước. Lớp gọi (FFI, test) gọi hàm này sau mỗi lần chạy lõi.
 */
void hal_host_sync_steps(hal_host_t *h, const struct fly_ctx *ctx);

/* Lớp gọi báo một lần NACK I2C để đếm vào stats. */
void hal_host_note_i2c_nack(hal_host_t *h);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_HAL_HOST_H */
