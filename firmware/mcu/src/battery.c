/*
 * battery.c — đọc ADC pin, nhân hệ số chia, đánh giá ngưỡng có hysteresis.
 */
#include "flytex/battery.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/power.h"
#include "flytex/regs_gen.h"

uint16_t fly_battery_mv(const fly_ctx_t *ctx)
{
    return ctx ? ctx->vbat_mv : 0u;
}

int fly_battery_valid(const fly_ctx_t *ctx)
{
    return ctx ? (int)ctx->vbat_valid : 0;
}

static void battery_eval(fly_ctx_t *ctx, uint32_t now)
{
    uint16_t mv = ctx->vbat_mv;

    /* Mọi ngưỡng dùng mẫu thô + đếm mẫu liên tiếp; EMA chỉ để hiển thị/log.
     * Cách này vẫn bỏ qua sụt áp ngắn mà không trễ 6-10 mẫu như lọc. */
    if (ctx->vbat_mv < (uint16_t)FLY_BATT_CUTOFF_MV) {
        if (ctx->batt_cut_n < 255u) {
            ctx->batt_cut_n++;
        }
        if (ctx->batt_cut_n < (uint8_t)FLY_BATT_CUTOFF_N) {
            return; /* chưa đủ số mẫu liên tiếp: có thể chỉ là sụt áp tải */
        }
        ctx->low_batt = 1u;
        fly_fault_set_active_batt(ctx, (uint8_t)FLY_FAULT_BATT_UNDERVOLTAGE);
        fly_power_enter_survival(ctx, (uint8_t)FLY_FAULT_NONE);
        return;
    }
    ctx->batt_cut_n = 0u;
    fly_fault_set_active_batt(ctx, (uint8_t)FLY_FAULT_NONE);

    if (mv < (uint16_t)FLY_BATT_WARN_MV) {
        ctx->batt_ok_n = 0u;
        if (ctx->batt_low_n < 255u) {
            ctx->batt_low_n++;
        }
        if (!ctx->low_batt && ctx->batt_low_n >= (uint8_t)FLY_BATT_WARN_N) {
            ctx->low_batt = 1u;
            fly_events_post(ctx, FLY_EVENT_LOW_BATT);
            fly_power_request_shutdown(ctx, now, 1u);
        }
    } else if (mv >= (uint16_t)FLY_BATT_RECOVER_MV) {
        ctx->batt_low_n = 0u;
        if (ctx->batt_ok_n < 255u) {
            ctx->batt_ok_n++;
        }
        if (ctx->low_batt && ctx->batt_ok_n >= (uint8_t)FLY_BATT_RECOVER_N) {
            ctx->low_batt = 0u;
        }
    } else {
        /* vùng hysteresis: không đổi trạng thái, không tích lũy */
        ctx->batt_low_n = 0u;
        ctx->batt_ok_n = 0u;
    }
}

static void battery_sample(fly_ctx_t *ctx, uint32_t now)
{
    uint32_t adc_mv = 0u;
    uint32_t mv;
    int rc;

    ctx->batt_next_ms = now + FLY_BATT_SAMPLE_MS;

    rc = ctx->hal->adc_mv(FLY_HAL(ctx), FLY_ADC_VBAT, &adc_mv);
    if (rc != FLY_OK) {
        /* Không đoán điện áp pin. Giữ giá trị cũ và ghi log. */
        fly_log_push(ctx, FLY_LOG_IO, (uint8_t)(-rc));
        return;
    }

    mv = (adc_mv * FLY_BATT_DIV_NUM + (FLY_BATT_DIV_DEN / 2u)) / FLY_BATT_DIV_DEN;
    if (mv > 65535u) {
        mv = 65535u;
    }
    ctx->vbat_mv = (uint16_t)mv;
    ctx->vbat_valid = 1u;
    if (ctx->vbat_filt_mv == 0u) {
        ctx->vbat_filt_mv = (uint16_t)mv;
    } else {
        ctx->vbat_filt_mv = (uint16_t)((ctx->vbat_filt_mv + mv) / 2u);
    }
    battery_eval(ctx, now);
}

void fly_battery_step(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    /* Sinh tồn: chỉ thức khi có VBUS, không lấy mẫu định kỳ (docs/14 §3.2). */
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    if (!fly_due(ctx->batt_next_ms, now)) {
        return;
    }
    battery_sample(ctx, now);
}

void fly_battery_force(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    battery_sample(ctx, now);
}

uint32_t fly_battery_next_timeout(const fly_ctx_t *ctx, uint32_t now)
{
    int32_t delta;

    if (!ctx) {
        return UINT32_MAX;
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return UINT32_MAX;
    }
    delta = (int32_t)(ctx->batt_next_ms - now);
    return (delta <= 0) ? 0u : (uint32_t)delta;
}
