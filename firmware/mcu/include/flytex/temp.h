/*
 * temp.h — đọc nhiệt độ pin và môi trường.
 *
 * temp_c(0) là NTC trên pack, temp_c(1) là DS18B20. Không đọc được (FLY_ENOSYS
 * hoặc lỗi khác) thì thanh ghi trả 0x80 và FAULT_CODE = SENSOR_STALE; tuyệt
 * đối không trả 25 °C.
 *
 * Quá nóng > 45 °C → BATT_OVERTEMP, quá lạnh < 0 °C → BATT_UNDERTEMP; cả hai
 * đặt bit CHARGE_INHIBIT và kéo chân FLY_PIN_CHG_INHIBIT. Hysteresis 2 °C.
 */
#ifndef FLYTEX_TEMP_H
#define FLYTEX_TEMP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Lấy mẫu nếu tới kỳ, cập nhật lỗi và chân cấm sạc. */
void fly_temp_step(struct fly_ctx *ctx, uint32_t now);

/* Lấy mẫu ngay. */
void fly_temp_force(struct fly_ctx *ctx, uint32_t now);

/* Số ms tới lần lấy mẫu kế tiếp. */
uint32_t fly_temp_next_timeout(const struct fly_ctx *ctx, uint32_t now);

/* Byte trả cho BAT_TEMP_C / AMB_TEMP_C (0x80 là không hợp lệ). */
uint8_t fly_temp_byte(int8_t value, uint8_t valid);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_TEMP_H */
