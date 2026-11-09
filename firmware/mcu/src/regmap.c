/*
 * regmap.c — hiện thực bảng thanh ghi sinh từ spec/registers.toml.
 *
 * Mỗi lần đọc/ghi một byte đều đi qua bảng fly_reg_descs: quyền truy cập và
 * kích thước nhóm lấy từ đó, không hard-code lại.
 */
#include "flytex/regmap.h"
#include "flytex/battery.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/nvm.h"
#include "flytex/power.h"
#include "flytex/regs_gen.h"
#include "flytex/sched.h"
#include "flytex/temp.h"

const fly_reg_desc_t *fly_reg_find(uint8_t addr)
{
    uint32_t i;

    for (i = 0; i < FLY_REG_DESC_COUNT; i++) {
        const fly_reg_desc_t *desc = &fly_reg_descs[i];
        if (addr >= desc->addr && (uint16_t)addr < (uint16_t)((uint16_t)desc->addr + desc->size)) {
            return desc;
        }
    }
    return NULL;
}

static uint32_t stage_be(const uint8_t *buf, uint8_t size)
{
    uint32_t value = 0u;
    uint8_t i;

    for (i = 0; i < size; i++) {
        value = (value << 8) | (uint32_t)buf[i];
    }
    return value;
}

static void seed_be(uint8_t *buf, uint8_t size, uint32_t value)
{
    uint8_t i;

    for (i = 0; i < size; i++) {
        buf[i] = (uint8_t)((value >> (8u * (uint32_t)(size - 1u - i))) & 0xFFu);
    }
}

static uint8_t read_vbat(fly_ctx_t *ctx, uint8_t off)
{
    if (off == 0u || !ctx->vbat_latched) {
        ctx->vbat_latch = ctx->vbat_mv;
        ctx->vbat_latched = 1u;
    }
    return (off == 0u) ? (uint8_t)((ctx->vbat_latch >> 8) & 0xFFu)
                       : (uint8_t)(ctx->vbat_latch & 0xFFu);
}

static uint8_t read_uptime(fly_ctx_t *ctx, uint8_t off, uint32_t now)
{
    if (off == 0u || !ctx->uptime_latched) {
        uint32_t seconds = (now - ctx->boot_ms) / 1000u;
        if (seconds > (uint32_t)FLY_UPTIME_SAT_S) {
            seconds = (uint32_t)FLY_UPTIME_SAT_S;
        }
        ctx->uptime_latch = (uint16_t)seconds;
        ctx->uptime_latched = 1u;
    }
    return (off == 0u) ? (uint8_t)((ctx->uptime_latch >> 8) & 0xFFu)
                       : (uint8_t)(ctx->uptime_latch & 0xFFu);
}

static uint8_t read_wake_in(fly_ctx_t *ctx, uint8_t off, uint32_t now)
{
    if (off == 0u || !ctx->wake_in_latched) {
        ctx->wake_in_latch_s = fly_sched_remaining_s(ctx, now);
        ctx->wake_in_latched = 1u;
    }
    return (uint8_t)((ctx->wake_in_latch_s >> (8u * (uint32_t)(3u - off))) & 0xFFu);
}

int fly_reg_read(fly_ctx_t *ctx, uint8_t addr, uint8_t *out)
{
    const fly_reg_desc_t *desc;
    uint8_t off;
    uint32_t now;

    if (!ctx || !out) {
        return FLY_EINVAL;
    }
    desc = fly_reg_find(addr);
    if (!desc) {
        return FLY_EIO;
    }
    if (desc->access == FLY_ACCESS_WO) {
        return FLY_EIO; /* đọc thanh ghi chỉ ghi: NACK */
    }
    off = (uint8_t)(addr - desc->addr);
    now = fly_now(ctx);

    switch (desc->addr) {
    case FLY_REG_PROTO_VER:
    case FLY_REG_FW_VER:
        *out = desc->reset;
        return FLY_OK;
    case FLY_REG_STATUS:
        *out = fly_status_byte(ctx);
        return FLY_OK;
    case FLY_REG_CHG:
        *out = fly_chg_byte(ctx);
        return FLY_OK;
    case FLY_REG_EVENT:
        *out = fly_events_read_clear(ctx);
        return FLY_OK;
    case FLY_REG_FAULT_CODE:
        *out = fly_fault_code(ctx);
        return FLY_OK;
    case FLY_REG_VBAT_MV:
        *out = read_vbat(ctx, off);
        return FLY_OK;
    case FLY_REG_BAT_TEMP_C:
        *out = fly_temp_byte(ctx->batt_temp_c, ctx->batt_temp_valid);
        return FLY_OK;
    case FLY_REG_AMB_TEMP_C:
        *out = fly_temp_byte(ctx->amb_temp_c, ctx->amb_temp_valid);
        return FLY_OK;
    case FLY_REG_MODE:
        *out = ctx->mode;
        return FLY_OK;
    case FLY_REG_WAKE_IN_S:
        *out = read_wake_in(ctx, off, now);
        return FLY_OK;
    case FLY_REG_EVENT_MASK:
        *out = ctx->event_mask;
        return FLY_OK;
    case FLY_REG_SYS_FLAGS:
        *out = fly_sys_flags_byte(ctx);
        return FLY_OK;
    case FLY_REG_WAKE_CHAN:
        *out = ctx->wake_chan;
        return FLY_OK;
    case FLY_REG_WAKE_PERIOD_S:
        *out = (off == 0u) ? (uint8_t)((ctx->wake_period_s >> 8) & 0xFFu)
                           : (uint8_t)(ctx->wake_period_s & 0xFFu);
        return FLY_OK;
    case FLY_REG_UPTIME_S:
        *out = read_uptime(ctx, off, now);
        return FLY_OK;
    case FLY_REG_BOOT_COUNT:
        *out = ctx->boot_count;
        return FLY_OK;
    default:
        return FLY_EIO;
    }
}

static void cmd_execute(fly_ctx_t *ctx, uint8_t value, uint32_t now)
{
    fly_log_push(ctx, FLY_LOG_CMD, value);
    switch (value) {
    case FLY_CMD_SOC_WAKE:
        fly_power_cmd_soc_wake(ctx, now);
        break;
    case FLY_CMD_SOC_SHUTDOWN_DONE:
        fly_power_cmd_shutdown_done(ctx, now);
        break;
    case FLY_CMD_MODEM_ON:
        fly_power_modem_set(ctx, 1);
        break;
    case FLY_CMD_MODEM_OFF:
        fly_power_modem_set(ctx, 0);
        break;
    case FLY_CMD_MODEM_RESET:
        fly_power_modem_pulse(ctx, now, FLY_PIN_MODEM_RESET);
        break;
    case FLY_CMD_CLEAR_FAULT:
        fly_fault_clear(ctx);
        break;
    case FLY_CMD_MODEM_PWRKEY:
        fly_power_modem_pulse(ctx, now, FLY_PIN_MODEM_PWRKEY);
        break;
    default:
        /* Mã lạ: không làm gì, chỉ đặt lỗi. */
        fly_fault_latch(ctx, (uint8_t)FLY_FAULT_BAD_CMD);
        break;
    }
}

static int write_wake_in(fly_ctx_t *ctx, uint8_t off, uint8_t value, uint32_t now)
{
    if (ctx->wake_in_stage_mask == 0u) {
        seed_be(ctx->wake_in_stage, 4u, fly_sched_remaining_s(ctx, now));
    }
    ctx->wake_in_stage[off] = value;
    ctx->wake_in_stage_mask = (uint8_t)(ctx->wake_in_stage_mask | (uint8_t)(1u << off));
    if (off == 3u) {
        uint32_t seconds = stage_be(ctx->wake_in_stage, 4u);
        ctx->wake_in_stage_mask = 0u;
        fly_sched_set_wake_in(ctx, seconds, now);
        (void)fly_nvm_save(ctx);
    }
    return FLY_OK;
}

static int write_wake_period(fly_ctx_t *ctx, uint8_t off, uint8_t value, uint32_t now)
{
    if (ctx->wake_period_stage_mask == 0u) {
        seed_be(ctx->wake_period_stage, 2u, (uint32_t)ctx->wake_period_s);
    }
    ctx->wake_period_stage[off] = value;
    ctx->wake_period_stage_mask = (uint8_t)(ctx->wake_period_stage_mask | (uint8_t)(1u << off));
    if (off == 1u) {
        ctx->wake_period_s = (uint16_t)stage_be(ctx->wake_period_stage, 2u);
        ctx->wake_period_stage_mask = 0u;
        fly_sched_rearm_chan(ctx, now);
        (void)fly_nvm_save(ctx);
    }
    return FLY_OK;
}

int fly_reg_write(fly_ctx_t *ctx, uint8_t addr, uint8_t value)
{
    const fly_reg_desc_t *desc;
    uint8_t off;
    uint32_t now;

    if (!ctx) {
        return FLY_EINVAL;
    }
    desc = fly_reg_find(addr);
    if (!desc) {
        return FLY_EIO;
    }
    if (desc->access == FLY_ACCESS_RO) {
        return FLY_EIO; /* ghi thanh ghi chỉ đọc: NACK */
    }
    off = (uint8_t)(addr - desc->addr);
    now = fly_now(ctx);

    switch (desc->addr) {
    case FLY_REG_CMD:
        cmd_execute(ctx, value, now);
        return FLY_OK;
    case FLY_REG_MODE:
        if (value > (uint8_t)FLY_MODE_WATCH) {
            return FLY_EINVAL;
        }
        ctx->mode = value;
        fly_power_apply_mode(ctx);
        (void)fly_nvm_save(ctx);
        return FLY_OK;
    case FLY_REG_WAKE_IN_S:
        return write_wake_in(ctx, off, value, now);
    case FLY_REG_EVENT_MASK:
        ctx->event_mask = value;
        fly_events_irq_update(ctx);
        return FLY_OK;
    case FLY_REG_WAKE_CHAN:
        if (value > (uint8_t)FLY_WAKE_CHAN_EDRX_MQTT) {
            return FLY_EINVAL;
        }
        ctx->wake_chan = value;
        fly_sched_rearm_chan(ctx, now);
        (void)fly_nvm_save(ctx);
        return FLY_OK;
    case FLY_REG_WAKE_PERIOD_S:
        return write_wake_period(ctx, off, value, now);
    default:
        return FLY_EIO;
    }
}
