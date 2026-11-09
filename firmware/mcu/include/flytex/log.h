/*
 * log.h — log vòng trong RAM của lõi.
 *
 * Mục đích: mỗi lỗi và mỗi quyết định nguồn đều để lại dấu vết đọc được khi
 * gỡ lỗi, không nuốt lỗi. Log nằm trong fly_ctx_t nên không cần biến toàn cục
 * và tự mất khi khởi động lại (đúng ý đồ: log vòng, không phải nơi lưu bền).
 * Không có thanh ghi I2C cho log trong spec/registers.toml — muốn đọc từ SoC
 * phải thêm thanh ghi ở spec trước.
 */
#ifndef FLYTEX_LOG_H
#define FLYTEX_LOG_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FLY_LOG_CAP 16u

/* Loại bản ghi. */
enum fly_log_code {
    FLY_LOG_BOOT = 1,   /* khởi động, arg = boot_count */
    FLY_LOG_STATE = 2,  /* đổi trạng thái nguồn, arg = trạng thái mới */
    FLY_LOG_EVENT = 3,  /* sự kiện, arg = bit EVENT */
    FLY_LOG_FAULT = 4,  /* lỗi, arg = FAULT_CODE */
    FLY_LOG_CMD = 5,    /* lệnh từ SoC, arg = mã lệnh */
    FLY_LOG_NVM = 6,    /* lưu/đọc NVM, arg = 0 lưu, 1 đọc hỏng */
    FLY_LOG_IO = 7      /* lỗi HAL, arg = mã lỗi (dạng uint8_t) */
};

typedef struct {
    uint8_t code;
    uint8_t arg;
    uint16_t seq;
    uint32_t ms;
} fly_log_entry_t;

/* Ghi một bản ghi; bản ghi cũ nhất bị ghi đè khi đầy. */
void fly_log_push(struct fly_ctx *ctx, uint8_t code, uint8_t arg);

/* Số bản ghi hiện có (0..FLY_LOG_CAP). */
uint8_t fly_log_count(const struct fly_ctx *ctx);

/*
 * Đọc bản ghi theo thứ tự cũ → mới, index 0 là cũ nhất.
 * Trả FLY_OK, hoặc FLY_EINVAL nếu index ngoài dải hoặc out NULL.
 */
int fly_log_get(const struct fly_ctx *ctx, uint8_t index, fly_log_entry_t *out);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_LOG_H */
