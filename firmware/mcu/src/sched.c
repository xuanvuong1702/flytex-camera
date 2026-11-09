/*
 * sched.c — lịch thức WAKE_IN_S và kênh đánh thức định kỳ WAKE_CHAN.
 */
#include "flytex/sched.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/nvm.h"
#include "flytex/power.h"
#include "flytex/regs_gen.h"

uint32_t fly_sched_period_s(const fly_ctx_t *ctx)
{
    uint32_t period;

    if (!ctx) {
        return FLY_WAKE_PERIOD_DEFAULT_S;
    }
    period = ctx->wake_period_s;
    return (period == 0u) ? (uint32_t)FLY_WAKE_PERIOD_DEFAULT_S : period;
}

void fly_sched_set_wake_in(fly_ctx_t *ctx, uint32_t seconds, uint32_t now)
{
    if (!ctx) {
        return;
    }
    if (seconds > (uint32_t)FLY_WAKE_IN_MAX_S) {
        seconds = (uint32_t)FLY_WAKE_IN_MAX_S;
    }
    ctx->wake_in_cfg_s = seconds;
    ctx->wake_in_latched = 0u;
    if (seconds == 0u) {
        ctx->wake_in_armed = 0u;
        ctx->wake_in_due_ms = now;
    } else {
        ctx->wake_in_due_ms = now + (seconds * 1000u);
        ctx->wake_in_armed = 1u;
    }
}

void fly_sched_rearm_chan(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    ctx->chan_wait_ready = 0u;
    if (ctx->wake_chan == (uint8_t)FLY_WAKE_CHAN_OFF) {
        ctx->chan_armed = 0u;
        return;
    }
    ctx->chan_armed = 1u;
    ctx->chan_due_ms = now + (fly_sched_period_s(ctx) * 1000u);
}

void fly_sched_init(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx) {
        return;
    }
    if (ctx->wake_in_cfg_s > 0u) {
        fly_sched_set_wake_in(ctx, ctx->wake_in_cfg_s, now);
    } else {
        ctx->wake_in_armed = 0u;
        ctx->wake_in_due_ms = now;
    }
    fly_sched_rearm_chan(ctx, now);
}

uint32_t fly_sched_remaining_s(const fly_ctx_t *ctx, uint32_t now)
{
    int32_t delta;

    if (!ctx || !ctx->wake_in_armed) {
        return 0u;
    }
    delta = (int32_t)(ctx->wake_in_due_ms - now);
    if (delta <= 0) {
        return 0u;
    }
    return ((uint32_t)delta + 999u) / 1000u;
}

void fly_sched_step(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx || !ctx->wake_in_armed) {
        return;
    }
    /* Sinh tồn chỉ thức khi có VBUS: giữ nguyên lịch, không xử lý ở đây. */
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return;
    }
    if (!fly_due(ctx->wake_in_due_ms, now)) {
        return;
    }
    ctx->wake_in_armed = 0u;
    ctx->wake_in_cfg_s = 0u;
    ctx->wake_in_latched = 0u;
    fly_events_post(ctx, FLY_EVENT_SCHEDULE);
    (void)fly_nvm_save(ctx);
    fly_power_request_wake(ctx, now);
}

static void sched_wake_alarm(fly_ctx_t *ctx, uint32_t now)
{
    ctx->chan_wait_ready = 0u;
    fly_events_post(ctx, FLY_EVENT_WAKE_ALARM);
    fly_power_request_wake(ctx, now);
}

void fly_sched_chan_step(fly_ctx_t *ctx, uint32_t now)
{
    if (!ctx || !ctx->chan_armed) {
        return;
    }
    /* Kênh chỉ có nghĩa khi SoC tắt; SoC đang chạy thì nó tự lo kết nối. */
    if (ctx->state != (uint8_t)FLY_ST_OFF) {
        return;
    }

    if (ctx->chan_wait_ready) {
        if (ctx->modem_status) {
            sched_wake_alarm(ctx, now);
            return;
        }
        if (fly_due(ctx->chan_ready_due_ms, now)) {
            fly_fault_latch(ctx, (uint8_t)FLY_FAULT_MODEM_NO_BOOT);
            sched_wake_alarm(ctx, now);
        }
        return;
    }

    if (!fly_due(ctx->chan_due_ms, now)) {
        return;
    }
    ctx->chan_due_ms = now + (fly_sched_period_s(ctx) * 1000u);

    if (ctx->wake_chan == (uint8_t)FLY_WAKE_CHAN_MODEM_TCP_POLL) {
        /*
         * Bật rail modem và chờ chân STATUS. MCU KHÔNG tự chạy TCP: sau khi
         * modem lên, MCU chỉ báo WAKE_ALARM để SoC thức và làm phần TCP.
         */
        fly_power_modem_set(ctx, 1);
        ctx->chan_wait_ready = 1u;
        ctx->chan_ready_due_ms = now + FLY_MODEM_READY_TIMEOUT_MS;
        return;
    }

    /* SMS / EDRX_MQTT: chưa có hành vi riêng trong đặc tả, chỉ báo sự kiện. */
    sched_wake_alarm(ctx, now);
}

uint32_t fly_sched_next_timeout(const fly_ctx_t *ctx, uint32_t now)
{
    int32_t delta;

    if (!ctx || !ctx->wake_in_armed) {
        return UINT32_MAX;
    }
    if (ctx->state == (uint8_t)FLY_ST_SURVIVAL) {
        return UINT32_MAX;
    }
    delta = (int32_t)(ctx->wake_in_due_ms - now);
    return (delta <= 0) ? 0u : (uint32_t)delta;
}

uint32_t fly_sched_chan_next_timeout(const fly_ctx_t *ctx, uint32_t now)
{
    int32_t delta;

    if (!ctx || !ctx->chan_armed) {
        return UINT32_MAX;
    }
    if (ctx->state != (uint8_t)FLY_ST_OFF) {
        return UINT32_MAX;
    }
    delta = (int32_t)((ctx->chan_wait_ready ? ctx->chan_ready_due_ms : ctx->chan_due_ms) - now);
    return (delta <= 0) ? 0u : (uint32_t)delta;
}
