/*
 * battery.h — đo và đánh giá điện áp pin.
 *
 * adc_mv() trả mV tại chân ADC (sau mạch chia); lõi nhân hệ số
 * FLY_BATT_DIV_NUM/DEN trong config.h để ra VBAT thật.
 *
 * Ngưỡng có hysteresis:
 *   - dưới WARN 3100 mV  → LOW_BATT (một lần mỗi lần vượt), yêu cầu SoC tắt;
 *   - dưới CUTOFF 2900 mV → cắt rail, vào sinh tồn;
 *   - từ RECOVER 3300 mV trở lên → xóa LOW_BATT.
 */
#ifndef FLYTEX_BATTERY_H
#define FLYTEX_BATTERY_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Lấy mẫu nếu tới kỳ; cập nhật ngưỡng, sự kiện và yêu cầu tắt máy. */
void fly_battery_step(struct fly_ctx *ctx, uint32_t now);

/* Lấy mẫu ngay, bỏ qua chu kỳ (dùng khi vừa thoát sinh tồn). */
void fly_battery_force(struct fly_ctx *ctx, uint32_t now);

/* Số ms tới lần lấy mẫu kế tiếp (UINT32_MAX nếu đang sinh tồn). */
uint32_t fly_battery_next_timeout(const struct fly_ctx *ctx, uint32_t now);

/* Điện áp pin đã nhân hệ số chia; 0 nếu chưa từng đọc được. */
uint16_t fly_battery_mv(const struct fly_ctx *ctx);

/* 1 nếu đã có ít nhất một lần đọc ADC thành công. */
int fly_battery_valid(const struct fly_ctx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_BATTERY_H */
