/* charger.c — cấu hình dòng sạc BQ25070 bằng 11 xung trên chân CTRL. */
#include "flytex/charger.h"
#include "flytex/config.h"

void fly_charger_program(fly_ctx_t *ctx, int pulses)
{
    int i;

    if (!ctx || !ctx->hal || pulses <= 0) {
        return;
    }
    /* CTRL thấp = cho phép sạc. Mỗi xung cao 200 us, thấp 200 us.
     * Sau chuỗi, giữ thấp >= 2 ms để chốt bảng xung (datasheet BQ25070). */
    ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_CHG_INHIBIT, 0);
    ctx->hal->delay_us(FLY_HAL(ctx), 100u);
    for (i = 0; i < pulses; i++) {
        ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_CHG_INHIBIT, 1);
        ctx->hal->delay_us(FLY_HAL(ctx), FLY_CHG_PULSE_US);
        ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_CHG_INHIBIT, 0);
        ctx->hal->delay_us(FLY_HAL(ctx), FLY_CHG_PULSE_US);
    }
    ctx->hal->delay_us(FLY_HAL(ctx), 2000u);
}
