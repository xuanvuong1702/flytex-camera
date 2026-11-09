/*
 * events.c — sự kiện, chân MCU_IRQ, các byte trạng thái và lỗi.
 */
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/regs_gen.h"

void fly_events_irq_update(fly_ctx_t *ctx)
{
    uint8_t desired;
    int level;

    if (!ctx) {
        return;
    }
    desired = (uint8_t)((ctx->event & ctx->event_mask) != 0u);
    if (desired == ctx->irq_level) {
        return;
    }
    level = desired ? (int)FLY_IRQ_ASSERT_LEVEL : (int)(FLY_IRQ_ASSERT_LEVEL ? 0 : 1);
    ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_IRQ, level);
    ctx->irq_level = desired;
}

void fly_events_post(fly_ctx_t *ctx, uint8_t bits)
{
    if (!ctx || bits == 0u) {
        return;
    }
    ctx->event = (uint8_t)(ctx->event | bits);
    fly_log_push(ctx, FLY_LOG_EVENT, bits);
    fly_events_irq_update(ctx);
}

uint8_t fly_events_read_clear(fly_ctx_t *ctx)
{
    uint8_t value;

    if (!ctx) {
        return 0u;
    }
    value = ctx->event;
    ctx->event = 0u;
    fly_events_irq_update(ctx);
    return value;
}

uint8_t fly_fault_code(const fly_ctx_t *ctx)
{
    if (!ctx) {
        return (uint8_t)FLY_FAULT_NONE;
    }
    if (ctx->fault_active_temp != (uint8_t)FLY_FAULT_NONE) {
        return ctx->fault_active_temp;
    }
    if (ctx->fault_active_batt != (uint8_t)FLY_FAULT_NONE) {
        return ctx->fault_active_batt;
    }
    return ctx->fault_latched;
}

void fly_fault_latch(fly_ctx_t *ctx, uint8_t code)
{
    if (!ctx || code == (uint8_t)FLY_FAULT_NONE) {
        return;
    }
    ctx->fault_latched = code;
    fly_log_push(ctx, FLY_LOG_FAULT, code);
}

void fly_fault_clear(fly_ctx_t *ctx)
{
    if (!ctx) {
        return;
    }
    ctx->fault_latched = (uint8_t)FLY_FAULT_NONE;
}

void fly_fault_set_active_temp(fly_ctx_t *ctx, uint8_t code)
{
    if (ctx) {
        ctx->fault_active_temp = code;
    }
}

void fly_fault_set_active_batt(fly_ctx_t *ctx, uint8_t code)
{
    if (ctx) {
        ctx->fault_active_batt = code;
    }
}

uint8_t fly_status_byte(const fly_ctx_t *ctx)
{
    uint8_t value = 0u;

    if (!ctx) {
        return 0u;
    }
    if (ctx->soc_ready) {
        value = (uint8_t)(value | FLY_STATUS_SOC_READY);
    }
    if (ctx->soc_pwr_on) {
        value = (uint8_t)(value | FLY_STATUS_SOC_POWER_ON);
    }
    if (ctx->modem_pwr_on) {
        value = (uint8_t)(value | FLY_STATUS_MODEM_POWER_ON);
    }
    if (fly_fault_code(ctx) != (uint8_t)FLY_FAULT_NONE) {
        value = (uint8_t)(value | FLY_STATUS_FAULT);
    }
    if (ctx->low_batt) {
        value = (uint8_t)(value | FLY_STATUS_LOW_BATT);
    }
    if (ctx->vbus_present) {
        value = (uint8_t)(value | FLY_STATUS_VBUS_PRESENT);
    }
    if (ctx->modem_status) {
        value = (uint8_t)(value | FLY_STATUS_MODEM_READY);
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        value = (uint8_t)(value | FLY_STATUS_SURVIVAL);
    }
    return value;
}

uint8_t fly_chg_byte(const fly_ctx_t *ctx)
{
    uint8_t value = 0u;

    if (!ctx) {
        return 0u;
    }
    if (ctx->charge_inhibit) {
        value = (uint8_t)(value | FLY_CHG_CHARGE_INHIBIT);
    }
    return value;
}

uint8_t fly_sys_flags_byte(const fly_ctx_t *ctx)
{
    uint8_t value;

    if (!ctx) {
        return 0u;
    }
    value = (uint8_t)(ctx->sys_flags & 0x0Fu);
    if (ctx->charge_inhibit) {
        value = (uint8_t)(value | FLY_SYS_FLAGS_CHG_INHIBIT);
    }
    return value;
}
