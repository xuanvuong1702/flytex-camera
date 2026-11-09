/*
 * events.h — sự kiện, lỗi, thanh ghi trạng thái và chân MCU_IRQ.
 *
 * EVENT là thanh ghi xóa khi đọc. MCU_IRQ kéo mức thấp khi có bit EVENT đã
 * đặt mà EVENT_MASK cho phép; thả ra khi không còn bit nào như vậy.
 */
#ifndef FLYTEX_EVENTS_H
#define FLYTEX_EVENTS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Đặt các bit sự kiện và cập nhật MCU_IRQ. */
void fly_events_post(struct fly_ctx *ctx, uint8_t bits);

/* Đọc EVENT rồi xóa (dùng cho regmap). */
uint8_t fly_events_read_clear(struct fly_ctx *ctx);

/* Tính lại mức chân MCU_IRQ từ event & event_mask. */
void fly_events_irq_update(struct fly_ctx *ctx);

/* Byte STATUS, CHG, SYS_FLAGS và FAULT_CODE. */
uint8_t fly_status_byte(const struct fly_ctx *ctx);
uint8_t fly_chg_byte(const struct fly_ctx *ctx);
uint8_t fly_sys_flags_byte(const struct fly_ctx *ctx);
uint8_t fly_fault_code(const struct fly_ctx *ctx);

/* Chốt một lỗi (giữ tới khi có CLEAR_FAULT hoặc lỗi khác). */
void fly_fault_latch(struct fly_ctx *ctx, uint8_t code);

/* Xóa lỗi đã chốt. Lỗi đang hoạt động do cảm biến/pin vẫn còn. */
void fly_fault_clear(struct fly_ctx *ctx);

/* Lỗi đang hoạt động, tự hết khi điều kiện hết (pin, nhiệt). */
void fly_fault_set_active_temp(struct fly_ctx *ctx, uint8_t code);
void fly_fault_set_active_batt(struct fly_ctx *ctx, uint8_t code);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_EVENTS_H */
