/*
 * temp.c — nhiệt độ pin (NTC) và môi trường (DS18B20), cấm sạc theo nhiệt.
 */
#include "flytex/temp.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/regs_gen.h"

uint8_t fly_temp_byte(int8_t value, uint8_t valid)
{
    if (!valid) {
        return (uint8_t)FLY_TEMP_INVALID_RAW;
    }
    return (uint8_t)value;
}

static void temp_store_invalid(fly_ctx_t *ctx, int sensor)
{
    if (sensor == FLY_TEMP_BATT) {
        ctx->batt_temp_valid = 0u;
        ctx->batt_temp_c = (int8_t)FLY_TEMP_INVALID;
    } else {
        ctx->amb_temp_valid = 0u;
        ctx->amb_temp_c = (int8_t)FLY_TEMP_INVALID;
    }
    fly_fault_latch(ctx, (uint8_t)FLY_FAULT_SENSOR_STALE);
}

static void temp_read_one(fly_ctx_t *ctx, int sensor)
{
    int8_t value = 0;
    int rc;

    rc = ctx->hal->temp_c(FLY_HAL(ctx), sensor, &value);
    if (rc != FLY_OK) {
        temp_store_invalid(ctx, sensor);
        fly_log_push(ctx, FLY_LOG_IO, (uint8_t)(-rc));
        return;
    }
    if (value == (int8_t)FLY_TEMP_INVALID) {
        temp_store_invalid(ctx, sensor);
        return;
    }
    if (sensor == FLY_TEMP_BATT) {
        ctx->batt_temp_c = value;
        ctx->batt_temp_valid = 1u;
    } else {
        ctx->amb_temp_c = value;
        ctx->amb_temp_valid = 1u;
    }
}

static void temp_update(fly_ctx_t *ctx)
{
    uint8_t inhibit;

    if (ctx->batt_temp_valid) {
        int t = (int)ctx->batt_temp_c;

        if (!ctx->over_temp && t > FLY_TEMP_HIGH_C) {
            ctx->over_temp = 1u;
        } else if (ctx->over_temp && t < FLY_TEMP_HIGH_CLEAR_C) {
            ctx->over_temp = 0u;
        }
        if (!ctx->under_temp && t < FLY_TEMP_LOW_C) {
            ctx->under_temp = 1u;
        } else if (ctx->under_temp && t > FLY_TEMP_LOW_CLEAR_C) {
            ctx->under_temp = 0u;
        }
    }

    if (ctx->over_temp) {
        fly_fault_set_active_temp(ctx, (uint8_t)FLY_FAULT_BATT_OVERTEMP);
    } else if (ctx->under_temp) {
        fly_fault_set_active_temp(ctx, (uint8_t)FLY_FAULT_BATT_UNDERTEMP);
    } else {
        fly_fault_set_active_temp(ctx, (uint8_t)FLY_FAULT_NONE);
    }

    /*
     * Không đọc được NTC thì cấm sạc: đó là hành vi an toàn, không phải đoán
     * nhiệt độ. Nhiệt độ môi trường thiếu chỉ ghi lỗi, không cấm sạc.
     */
    inhibit = (uint8_t)((ctx->batt_temp_valid == 0u) || ctx->over_temp || ctx->under_temp);
    if (inhibit != ctx->charge_inhibit) {
        int level = inhibit ? (int)FLY_CHG_INHIBIT_LEVEL
                            : (int)(FLY_CHG_INHIBIT_LEVEL ? 0 : 1);
        ctx->charge_inhibit = inhibit;
        ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_CHG_INHIBIT, level);
    }
}

static void temp_sample(fly_ctx_t *ctx, uint32_t now)
{
    ctx->temp_next_ms = now + FLY_TEMP_SAMPLE_MS;
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    temp_read_one(ctx, FLY_TEMP_BATT);
    temp_read_one(ctx, FLY_TEMP_AMB);
    temp_update(ctx);
}

void fly_temp_step(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    if (!fly_due(ctx->temp_next_ms, now)) {
        return;
    }
    temp_sample(ctx, now);
}

void fly_temp_force(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    temp_sample(ctx, now);
}

uint32_t fly_temp_next_timeout(const fly_ctx_t *ctx, uint32_t now)
{
    int32_t delta;

    if (!ctx) {
        return UINT32_MAX;
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return UINT32_MAX;
    }
    delta = (int32_t)(ctx->temp_next_ms - now);
    return (delta <= 0) ? 0u : (uint32_t)delta;
}
