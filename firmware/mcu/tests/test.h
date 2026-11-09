/*
 * test.h — framework kiểm thử tối giản, tự đăng ký và tự chạy.
 *
 * Mỗi file test dùng TEST_CASE(tên) { ... }. Hàm đăng ký có thuộc tính
 * constructor nên chạy trước main; main nằm ở tests/test_main.c.
 *
 * Chỉ in ASCII ra stdout: console Windows không ổn định với UTF-8.
 */
#ifndef FLYTEX_TEST_H
#define FLYTEX_TEST_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "flytex/config.h"
#include "flytex/core.h"
#include "flytex/hal.h"

#define TEST_MAX_CASES 128

typedef void (*fly_test_fn)(void);

extern const char *fly_test_current;
extern int fly_test_checks;
extern int fly_test_failures;

void fly_test_register(const char *name, fly_test_fn fn);

#define TEST_CASE(fn)                                                    \
    static void fn(void);                                                \
    static void fn##_register(void) __attribute__((constructor, used));  \
    static void fn##_register(void) { fly_test_register(#fn, fn); }      \
    static void fn(void)

#define TEST_ASSERT(cond)                                                          \
    do {                                                                           \
        fly_test_checks++;                                                         \
        if (!(cond)) {                                                             \
            fly_test_failures++;                                                   \
            printf("FAIL %s: line %d: expected %s\n", fly_test_current, __LINE__,  \
                   #cond);                                                         \
        }                                                                          \
    } while (0)

#define TEST_ASSERT_EQ(expect, actual)                                             \
    do {                                                                           \
        long test_e_ = (long)(expect);                                             \
        long test_a_ = (long)(actual);                                             \
        fly_test_checks++;                                                         \
        if (test_e_ != test_a_) {                                                  \
            fly_test_failures++;                                                   \
            printf("FAIL %s: line %d: expected %ld, got %ld\n", fly_test_current,  \
                   __LINE__, test_e_, test_a_);                                    \
        }                                                                          \
    } while (0)

/* Đọc/ghi một thanh ghi cho gọn. Lỗi đọc trả 0xEE để dễ thấy trong log. */
static inline uint8_t t_rd(fly_ctx_t *ctx, uint8_t reg)
{
    uint8_t value = 0u;

    if (fly_i2c_read(ctx, reg, &value, 1u) != FLY_OK) {
        return 0xEEu;
    }
    return value;
}

static inline int t_wr(fly_ctx_t *ctx, uint8_t reg, uint8_t value)
{
    return fly_i2c_write(ctx, reg, &value, 1u);
}

/* Đọc nhiều byte liên tiếp (để kiểm tra commit/latch). */
static inline int t_rd_block(fly_ctx_t *ctx, uint8_t reg, uint8_t *buf, uint8_t len)
{
    return fly_i2c_read(ctx, reg, buf, len);
}

static inline uint32_t t_rd32_be(fly_ctx_t *ctx, uint8_t reg)
{
    uint8_t buf[4] = {0u, 0u, 0u, 0u};

    if (fly_i2c_read(ctx, reg, buf, 4u) != FLY_OK) {
        return 0xFFFFFFFFu;
    }
    return ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
           ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
}

static inline uint16_t t_rd16_be(fly_ctx_t *ctx, uint8_t reg)
{
    uint8_t hi = 0u;
    uint8_t lo = 0u;

    /* Đọc từng byte để kiểm tra đúng cơ chế latch của nhóm 2 byte. */
    if (fly_i2c_read(ctx, reg, &hi, 1u) != FLY_OK) {
        return 0xFFFFu;
    }
    if (fly_i2c_read(ctx, (uint8_t)(reg + 1u), &lo, 1u) != FLY_OK) {
        return 0xFFFFu;
    }
    return (uint16_t)(((uint16_t)hi << 8) | (uint16_t)lo);
}

static inline void t_wr16_be(fly_ctx_t *ctx, uint8_t reg, uint16_t value)
{
    uint8_t buf[2];

    buf[0] = (uint8_t)((value >> 8) & 0xFFu);
    buf[1] = (uint8_t)(value & 0xFFu);
    (void)fly_i2c_write(ctx, reg, buf, 2u);
}

static inline void t_wr32_be(fly_ctx_t *ctx, uint8_t reg, uint32_t value)
{
    uint8_t buf[4];

    buf[0] = (uint8_t)((value >> 24) & 0xFFu);
    buf[1] = (uint8_t)((value >> 16) & 0xFFu);
    buf[2] = (uint8_t)((value >> 8) & 0xFFu);
    buf[3] = (uint8_t)(value & 0xFFu);
    (void)fly_i2c_write(ctx, reg, buf, 4u);
}

#endif /* FLYTEX_TEST_H */
