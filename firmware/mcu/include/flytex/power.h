/*
 * power.h — máy trạng thái nguồn phía MCU.
 *
 * Bật SoC: kéo +5V_SOC, chờ SOC_READY (hoặc CMD SOC_WAKE) tối đa 20 s.
 * Quá hạn → FAULT SOC_NO_BOOT, thử lại có giới hạn rồi vào sinh tồn.
 *
 * Tắt máy: đặt EVENT SHUTDOWN_REQ, chờ CMD SOC_SHUTDOWN_DONE tối đa 10 s,
 * sau khi có DONE thì chờ thêm 500 ms rồi cắt rail. Quá hạn → cắt cưỡng bức
 * và FAULT SOC_NO_HANDSHAKE.
 *
 * Sinh tồn: cắt cả hai rail, chỉ thức khi có VBUS.
 */
#ifndef FLYTEX_POWER_H
#define FLYTEX_POWER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Khôi phục rail theo mode và đặt trạng thái ban đầu. */
void fly_power_init(struct fly_ctx *ctx, uint32_t now);

/* Bước của máy trạng thái (hạn bắt tay, thử lại, cắt rail). */
void fly_power_step(struct fly_ctx *ctx, uint32_t now);

/* Đánh thức SoC: bật rail và bắt đầu chờ SOC_READY. */
void fly_power_request_wake(struct fly_ctx *ctx, uint32_t now);

/* Yêu cầu SoC tắt an toàn; kill_modem = 1 thì cắt luôn rail modem khi cắt. */
void fly_power_request_shutdown(struct fly_ctx *ctx, uint32_t now, uint8_t kill_modem);

/* Vào sinh tồn: cắt hết rail, chỉ còn VBUS đánh thức. */
void fly_power_enter_survival(struct fly_ctx *ctx, uint8_t fault);

/* Thoát sinh tồn khi có VBUS (đã lấy mẫu lại pin). */
void fly_power_exit_survival(struct fly_ctx *ctx, uint32_t now);

/* Lệnh CMD từ SoC. */
void fly_power_cmd_soc_wake(struct fly_ctx *ctx, uint32_t now);
void fly_power_cmd_shutdown_done(struct fly_ctx *ctx, uint32_t now);
void fly_power_modem_set(struct fly_ctx *ctx, int on);
void fly_power_modem_pulse(struct fly_ctx *ctx, uint32_t now, int pin);
void fly_power_pulse_step(struct fly_ctx *ctx, uint32_t now);

/* Hạn kế tiếp của máy trạng thái (UINT32_MAX nếu không hẹn). */
uint32_t fly_power_next_timeout(const struct fly_ctx *ctx, uint32_t now);

/* Áp dụng mode hiện tại cho rail modem (Watch giữ modem, Eco tắt). */
void fly_power_apply_mode(struct fly_ctx *ctx);

/* 1 nếu SoC đang được cấp nguồn. */
int fly_power_soc_on(const struct fly_ctx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_POWER_H */
