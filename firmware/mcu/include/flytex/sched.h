/*
 * sched.h — lịch thức (WAKE_IN_S) và kênh đánh thức (WAKE_CHAN).
 *
 * WAKE_IN_S là số giây đếm ngược theo thời gian thực. Hết giờ → EVENT
 * SCHEDULE, giá trị về 0, lưu NVM, và MCU đánh thức SoC.
 *
 * WAKE_CHAN chạy định kỳ theo WAKE_PERIOD_S khi SoC đang tắt:
 *   - MODEM_TCP_POLL: bật rail modem, chờ chân STATUS modem (tối đa 30 s),
 *     rồi đặt EVENT WAKE_ALARM và đánh thức SoC. MCU KHÔNG tự chạy TCP;
 *     phần TCP/cloud nằm ở SoC.
 *   - SMS: cạnh lên của chân MODEM_RI (J_B2B chân 21) đặt EVENT WAKE_ALARM và
 *     đánh thức SoC; ngoài ra vẫn có nhịp WAKE_ALARM định kỳ theo chu kỳ.
 *     Cạnh RI khi WAKE_CHAN khác SMS bị bỏ qua.
 *   - EDRX_MQTT: chỉ đặt EVENT WAKE_ALARM theo chu kỳ (hành vi riêng của kênh
 *     này chưa có trong đặc tả, xem README).
 */
#ifndef FLYTEX_SCHED_H
#define FLYTEX_SCHED_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Nạp lịch từ cấu hình NVM (gọi trong fly_init). */
void fly_sched_init(struct fly_ctx *ctx, uint32_t now);

/* Đếm ngược tới hạn và xử lý khi hết giờ. */
void fly_sched_step(struct fly_ctx *ctx, uint32_t now);

/* Số giây còn lại của WAKE_IN_S (0 nếu đang tắt). */
uint32_t fly_sched_remaining_s(const struct fly_ctx *ctx, uint32_t now);

/* Đặt lại WAKE_IN_S (đã commit), tính hạn mới từ now. */
void fly_sched_set_wake_in(struct fly_ctx *ctx, uint32_t seconds, uint32_t now);

/* Bật/tắt và đặt lại chu kỳ kênh đánh thức khi cấu hình đổi. */
void fly_sched_rearm_chan(struct fly_ctx *ctx, uint32_t now);

/* Bước của kênh đánh thức. */
void fly_sched_chan_step(struct fly_ctx *ctx, uint32_t now);

/* Hạn kế tiếp của lịch (UINT32_MAX nếu không hẹn). */
uint32_t fly_sched_next_timeout(const struct fly_ctx *ctx, uint32_t now);
uint32_t fly_sched_chan_next_timeout(const struct fly_ctx *ctx, uint32_t now);

/* Chu kỳ hiệu dụng của kênh, giây. */
uint32_t fly_sched_period_s(const struct fly_ctx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_SCHED_H */
