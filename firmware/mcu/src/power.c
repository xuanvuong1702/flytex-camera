/*
 * power.c — máy trạng thái nguồn: bật SoC, bắt tay tắt máy, sinh tồn.
 */
#include "flytex/power.h"
#include "flytex/battery.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/regs_gen.h"

static int on_level(void)
{
    return (int)FLY_RAIL_ON_LEVEL;
}

static int off_level(void)
{
    return FLY_RAIL_ON_LEVEL ? 0 : 1;
}

static void rail_soc(fly_ctx_t *ctx, int on)
{
    ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_SOC_PWR, on ? on_level() : off_level());
    ctx->soc_pwr_on = (uint8_t)(on ? 1 : 0);
}

static void rail_modem(fly_ctx_t *ctx, int on)
{
    ctx->hal->gpio_write(FLY_HAL(ctx), FLY_PIN_MODEM_PWR, on ? on_level() : off_level());
    ctx->modem_pwr_on = (uint8_t)(on ? 1 : 0);
}

static void state_set(fly_ctx_t *ctx, uint8_t state)
{
    ctx->state = state;
    fly_log_push(ctx, FLY_LOG_STATE, state);
}

void fly_power_init(fly_ctx_t *ctx, uint32_t now)
{
    (void)now;
    if (!ctx) {
        return;
    }
    ctx->soc_ready = 0u;
    ctx->boot_attempts = 0u;
    rail_soc(ctx, 0);
    rail_modem(ctx, 0);
    state_set(ctx, (uint8_t)FLY_ST_OFF);
    fly_power_apply_mode(ctx);
}

void fly_power_apply_mode(fly_ctx_t *ctx)
{
    if (!ctx) {
        return;
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    /* Khi SoC đang chạy, chính SoC quyết định rail modem; mode chỉ áp lúc ngủ. */
    if (ctx->state != (uint8_t)FLY_ST_OFF && ctx->state != (uint8_t)FLY_ST_RETRY) {
        return;
    }
    rail_modem(ctx, ctx->mode == (uint8_t)FLY_MODE_WATCH);
}

static void power_on_soc(fly_ctx_t *ctx, uint32_t now)
{
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    ctx->boot_attempts = (uint8_t)(ctx->boot_attempts + 1u);
    ctx->soc_ready = 0u;
    ctx->boot_due_ms = now + FLY_SOC_BOOT_TIMEOUT_MS;
    ctx->boot_armed = 1u;
    ctx->retry_armed = 0u;
    rail_soc(ctx, 1);
    state_set(ctx, (uint8_t)FLY_ST_BOOT);
}

void fly_power_request_wake(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    if (ctx->state != (uint8_t)FLY_ST_OFF && ctx->state != (uint8_t)FLY_ST_RETRY) {
        return;
    }
    ctx->boot_attempts = 0u;
    power_on_soc(ctx, now);
}

static void power_cut(fly_ctx_t *ctx)
{
    ctx->boot_armed = 0u;
    ctx->retry_armed = 0u;
    ctx->shutdown_armed = 0u;
    ctx->cut_armed = 0u;
    ctx->boot_attempts = 0u;
    rail_soc(ctx, 0);
    ctx->soc_ready = 0u;
    if (ctx->shutdown_kill_modem) {
        rail_modem(ctx, 0);
    }
    ctx->shutdown_kill_modem = 0u;
    state_set(ctx, (uint8_t)FLY_ST_OFF);
}

void fly_power_request_shutdown(fly_ctx_t *ctx, uint32_t now, uint8_t kill_modem)
{
    if (!ctx) {
        return;
    }
    if (ctx->state == (uint8_t)FLY_ST_ON) {
        ctx->shutdown_kill_modem = (uint8_t)(kill_modem ? 1u : 0u);
        ctx->shutdown_due_ms = now + FLY_SHUTDOWN_TIMEOUT_MS;
        ctx->shutdown_armed = 1u;
        ctx->cut_armed = 0u;
        state_set(ctx, (uint8_t)FLY_ST_SHUTDOWN);
        fly_events_post(ctx, FLY_EVENT_SHUTDOWN_REQ);
    } else if (ctx->state == (uint8_t)FLY_ST_BOOT || ctx->state == (uint8_t)FLY_ST_RETRY) {
        /* Chưa có gì để SoC kịp đóng file: cắt luôn. */
        ctx->boot_armed = 0u;
        ctx->retry_armed = 0u;
        ctx->boot_attempts = 0u;
        rail_soc(ctx, 0);
        ctx->soc_ready = 0u;
        if (kill_modem) {
            rail_modem(ctx, 0);
        }
        state_set(ctx, (uint8_t)FLY_ST_OFF);
    }
}

void fly_power_enter_survival(fly_ctx_t *ctx, uint8_t fault)
{
    if (!ctx) {
        return;
    }
    ctx->boot_armed = 0u;
    ctx->retry_armed = 0u;
    ctx->shutdown_armed = 0u;
    ctx->cut_armed = 0u;
    ctx->chan_wait_ready = 0u;
    ctx->boot_attempts = 0u;
    ctx->soc_ready = 0u;
    rail_soc(ctx, 0);
    rail_modem(ctx, 0);
    if (fault != (uint8_t)FLY_FAULT_NONE) {
        fly_fault_latch(ctx, fault);
    }
    if (ctx->state != (uint8_t)FLY_ST_SURVIVAL) {
        state_set(ctx, (uint8_t)FLY_ST_SURVIVAL);
    }
}

void fly_power_exit_survival(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx || ctx->state != (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    state_set(ctx, (uint8_t)FLY_ST_OFF);
    fly_power_apply_mode(ctx);
    /* Có VBUS: đánh giá lại pin ngay thay vì chờ kỳ lấy mẫu. */
    fly_battery_force(ctx, now);
}

void fly_power_cmd_soc_wake(fly_ctx_t *ctx, uint32_t now)
{
    (void)now;
    if (!ctx || ctx->state == (uint8_t)FLY_ST_SHUTDOWN) {
        return; /* đang tắt máy: không nhận lệnh "đã thức" nữa */
    }
    ctx->soc_ready = 1u;
    if (ctx->state == (uint8_t)FLY_ST_BOOT) {
        ctx->boot_armed = 0u;
        ctx->boot_attempts = 0u;
        state_set(ctx, (uint8_t)FLY_ST_ON);
    } else if (ctx->state == (uint8_t)FLY_ST_OFF || ctx->state == (uint8_t)FLY_ST_RETRY) {
        /* SoC báo đã thức khi MCU chưa bật rail: bật rail và coi như xong. */
        ctx->retry_armed = 0u;
        ctx->boot_armed = 0u;
        ctx->boot_attempts = 0u;
        rail_soc(ctx, 1);
        state_set(ctx, (uint8_t)FLY_ST_ON);
    }
}

void fly_power_cmd_shutdown_done(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx || ctx->state != (uint8_t)FLY_ST_SHUTDOWN) {
        return;
    }
    ctx->shutdown_armed = 0u;
    if (!ctx->cut_armed) {
        ctx->cut_armed = 1u;
        ctx->cut_due_ms = now + FLY_SHUTDOWN_CUT_DELAY_MS;
    }
}

void fly_power_modem_set(fly_ctx_t *ctx, int on)
{
    if (!ctx) {
        return;
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        rail_modem(ctx, 0);
        return;
    }
    rail_modem(ctx, on);
}

void fly_power_modem_pulse(fly_ctx_t *ctx, uint32_t now, int pin)
{
    uint32_t width;
    int active;

    if (!ctx || ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    if (pin == FLY_PIN_MODEM_PWRKEY) {
        width = FLY_MODEM_PWRKEY_PULSE_MS;
        active = (int)FLY_MODEM_PWRKEY_ACTIVE_LEVEL;
    } else if (pin == FLY_PIN_MODEM_RESET) {
        width = FLY_MODEM_RESET_PULSE_MS;
        active = (int)FLY_MODEM_RESET_ACTIVE_LEVEL;
    } else {
        return;
    }
    ctx->hal->gpio_write(FLY_HAL(ctx), pin, active);
    ctx->pulse_pin = (uint8_t)pin;
    ctx->pulse_due_ms = now + width;
    ctx->pulse_armed = 1u;
}

void fly_power_pulse_step(fly_ctx_t *ctx, uint32_t now)
{
    int idle;

    if (!ctx || !ctx->pulse_armed) {
        return;
    }
    if (!fly_due(ctx->pulse_due_ms, now)) {
        return;
    }
    if (ctx->pulse_pin == (uint8_t)FLY_PIN_MODEM_PWRKEY) {
        idle = FLY_MODEM_PWRKEY_ACTIVE_LEVEL ? 0 : 1;
    } else {
        idle = FLY_MODEM_RESET_ACTIVE_LEVEL ? 0 : 1;
    }
    ctx->hal->gpio_write(FLY_HAL(ctx), ctx->pulse_pin, idle);
    ctx->pulse_armed = 0u;
}

void fly_power_step(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    switch (ctx->state) {
    case FLY_ST_BOOT:
        if (ctx->hal->gpio_read(FLY_HAL(ctx), FLY_PIN_SOC_READY)) {
            ctx->soc_ready = 1u;
            ctx->boot_armed = 0u;
            ctx->boot_attempts = 0u;
            state_set(ctx, (uint8_t)FLY_ST_ON);
            break;
        }
        if (fly_due(ctx->boot_due_ms, now)) {
            ctx->boot_armed = 0u;
            rail_soc(ctx, 0);
            ctx->soc_ready = 0u;
            fly_fault_latch(ctx, (uint8_t)FLY_FAULT_SOC_NO_BOOT);
            if (ctx->boot_attempts <= (uint8_t)FLY_SOC_BOOT_RETRIES) {
                ctx->retry_due_ms = now + FLY_SOC_RETRY_DELAY_MS;
                ctx->retry_armed = 1u;
                state_set(ctx, (uint8_t)FLY_ST_RETRY);
            } else {
                fly_power_enter_survival(ctx, (uint8_t)FLY_FAULT_SOC_NO_BOOT);
            }
        }
        break;
    case FLY_ST_RETRY:
        if (ctx->retry_armed && fly_due(ctx->retry_due_ms, now)) {
            ctx->retry_armed = 0u;
            power_on_soc(ctx, now);
        }
        break;
    case FLY_ST_SHUTDOWN:
        if (ctx->cut_armed && fly_due(ctx->cut_due_ms, now)) {
            power_cut(ctx);
        } else if (ctx->shutdown_armed && fly_due(ctx->shutdown_due_ms, now)) {
            ctx->shutdown_armed = 0u;
            fly_fault_latch(ctx, (uint8_t)FLY_FAULT_SOC_NO_HANDSHAKE);
            power_cut(ctx);
        }
        break;
    case FLY_ST_SURVIVAL:
        /* Chỉ thoát khi có VBUS, xử lý ở core.c (sample_inputs). */
        break;
    default:
        break;
    }
}

uint32_t fly_power_next_timeout(const fly_ctx_t *ctx, uint32_t now)
{
    uint32_t best = UINT32_MAX;
    uint32_t candidates[4];
    uint8_t armed[4];
    uint32_t i;

    if (!ctx) {
        return best;
    }
    candidates[0] = ctx->boot_due_ms;
    armed[0] = ctx->boot_armed;
    candidates[1] = ctx->retry_due_ms;
    armed[1] = ctx->retry_armed;
    candidates[2] = ctx->shutdown_armed ? ctx->shutdown_due_ms : ctx->cut_due_ms;
    armed[2] = (uint8_t)(ctx->shutdown_armed || ctx->cut_armed);
    candidates[3] = ctx->pulse_due_ms;
    armed[3] = ctx->pulse_armed;

    for (i = 0; i < 4u; i++) {
        int32_t delta;
        uint32_t rel;
        if (!armed[i]) {
            continue;
        }
        delta = (int32_t)(candidates[i] - now);
        rel = (delta <= 0) ? 0u : (uint32_t)delta;
        if (rel < best) {
            best = rel;
        }
    }
    return best;
}

int fly_power_soc_on(const fly_ctx_t *ctx)
{
    return ctx ? (int)ctx->soc_pwr_on : 0;
}
