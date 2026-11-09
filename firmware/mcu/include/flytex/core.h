/*
 * core.h — API công khai của lõi MCU giám sát.
 *
 * Đây là bề mặt dùng cho HAL thật, cho thư viện mô phỏng (sim/ffi.c) và cho
 * kiểm thử host. Trạng thái hoàn toàn nằm trong fly_ctx_t; không có biến
 * toàn cục nào ngoài bảng hằng fly_reg_descs trong regs_gen.c.
 */
#ifndef FLYTEX_CORE_H
#define FLYTEX_CORE_H

#include <stdint.h>

#include "flytex/hal.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fly_ctx fly_ctx_t;

/*
 * Khởi tạo lõi: đọc NVM (mode, wake_in_s, wake_chan, wake_period_s,
 * boot_count), tăng boot_count, đặt SYS_FLAGS từ hal->reset_cause() và khôi
 * phục rail theo mode (Watch giữ modem, Eco tắt cả hai).
 *
 * Trả NULL nếu hal thiếu hàm bắt buộc hoặc hết bộ nhớ.
 */
fly_ctx_t *fly_init(const fly_hal_t *hal);

/*
 * Một bước xử lý: watchdog, lấy mẫu đầu vào (VBUS, modem STATUS, PIR), pin,
 * nhiệt, lịch, kênh đánh thức, máy trạng thái nguồn và cập nhật MCU_IRQ.
 * Không chặn, không ngủ, không gọi delay.
 */
void fly_step(fly_ctx_t *ctx);

/*
 * Số mili giây tới công việc kế tiếp; 0 nghĩa là phải gọi fly_step ngay.
 * Trả UINT32_MAX khi không có hẹn giờ nào (chỉ thức bởi nguồn ngoài).
 */
uint32_t fly_next_timeout_ms(fly_ctx_t *ctx);

/*
 * Vòng tickless: lặp fly_step + fly_next_timeout_ms + enter_stop cho tới khi
 * trôi đủ max_ms. Không có tick 1 ms; không có delay.
 */
void fly_run_slice(fly_ctx_t *ctx, uint32_t max_ms);

/*
 * Truy cập regmap như một slave I2C. Trả FLY_OK hoặc số âm:
 *   FLY_EIO    — NACK: địa chỉ ngoài dải, thanh ghi không định nghĩa,
 *                ghi vào thanh ghi chỉ đọc, đọc thanh ghi chỉ ghi;
 *   FLY_EINVAL — tham số sai (buf NULL, len 0, giá trị MODE/WAKE_CHAN lạ).
 */
int fly_i2c_read(fly_ctx_t *ctx, uint8_t reg, uint8_t *buf, uint8_t len);
int fly_i2c_write(fly_ctx_t *ctx, uint8_t reg, const uint8_t *buf, uint8_t len);

/* Giải phóng lõi. An toàn với NULL. */
void fly_destroy(fly_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_CORE_H */
