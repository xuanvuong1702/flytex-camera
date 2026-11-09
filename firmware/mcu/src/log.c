/*
 * log.c — log vòng trong RAM.
 */
#include "flytex/ctx.h"
#include "flytex/log.h"

void fly_log_push(fly_ctx_t *ctx, uint8_t code, uint8_t arg)
{
    fly_log_entry_t *slot;

    if (!ctx) {
        return;
    }
    slot = &ctx->log[ctx->log_head];
    slot->code = code;
    slot->arg = arg;
    slot->seq = ctx->log_seq;
    slot->ms = fly_now(ctx);
    ctx->log_seq = (uint16_t)(ctx->log_seq + 1u);

    ctx->log_head = (uint8_t)((ctx->log_head + 1u) % FLY_LOG_CAP);
    if (ctx->log_count < (uint8_t)FLY_LOG_CAP) {
        ctx->log_count = (uint8_t)(ctx->log_count + 1u);
    }
}

uint8_t fly_log_count(const fly_ctx_t *ctx)
{
    return ctx ? ctx->log_count : 0u;
}

int fly_log_get(const fly_ctx_t *ctx, uint8_t index, fly_log_entry_t *out)
{
    uint8_t start;

    if (!ctx || !out || index >= ctx->log_count) {
        return FLY_EINVAL;
    }
    start = (uint8_t)((ctx->log_head + (uint8_t)FLY_LOG_CAP - ctx->log_count) % FLY_LOG_CAP);
    *out = ctx->log[(uint8_t)((start + index) % FLY_LOG_CAP)];
    return FLY_OK;
}
