/*
 * core.c — khởi tạo, vòng tickless, điều phối các module.
 *
 * Không có while(1) với delay, không có counter 1 ms: mỗi bước chỉ xử lý việc
 * đã tới hạn rồi tính hạn kế tiếp để vào STOP.
 */
#include <stdlib.h>

#include "flytex/battery.h"
#include "flytex/core.h"
#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/nvm.h"
#include "flytex/power.h"
#include "flytex/regmap.h"
#include "flytex/regs_gen.h"
#include "flytex/sched.h"
#include "flytex/temp.h"
#include <stddef.h>

static int hal_valid(const fly_hal_t *hal)
{
    if (!hal) {
        return 0;
    }
    return hal->millis != NULL && hal->enter_stop != NULL && hal->gpio_read != NULL &&
           hal->gpio_write != NULL && hal->adc_mv != NULL && hal->temp_c != NULL &&
           hal->nvm_read != NULL && hal->nvm_write != NULL && hal->wdg_kick != NULL &&
           hal->epoch_s != NULL && hal->reset_cause != NULL;
}

static void drive_idle_outputs(fly_ctx_t *ctx)
{
    const fly_hal_t *hal = ctx->hal;
    void *h = FLY_HAL(ctx);

    hal->gpio_write(h, FLY_PIN_SOC_PWR, FLY_RAIL_ON_LEVEL ? 0 : 1);
    hal->gpio_write(h, FLY_PIN_MODEM_PWR, FLY_RAIL_ON_LEVEL ? 0 : 1);
    hal->gpio_write(h, FLY_PIN_IRQ, FLY_IRQ_ASSERT_LEVEL ? 0 : 1);
    hal->gpio_write(h, FLY_PIN_IR_LED, 0);
    hal->gpio_write(h, FLY_PIN_CHG_INHIBIT, FLY_CHG_INHIBIT_LEVEL ? 0 : 1);
    hal->gpio_write(h, FLY_PIN_MODEM_RESET, FLY_MODEM_RESET_ACTIVE_LEVEL ? 0 : 1);
    hal->gpio_write(h, FLY_PIN_MODEM_PWRKEY, FLY_MODEM_PWRKEY_ACTIVE_LEVEL ? 0 : 1);
    ctx->irq_level = 0u;
}

static void load_config(fly_ctx_t *ctx)
{
    fly_nvm_cfg_t cfg;
    int rc;

    rc = fly_nvm_load(ctx, &cfg);
    if (rc == FLY_OK) {
        ctx->mode = cfg.mode;
        ctx->wake_chan = cfg.wake_chan;
        ctx->wake_period_s = cfg.wake_period_s;
        ctx->wake_in_cfg_s = cfg.wake_in_s;
        ctx->boot_count = cfg.boot_count;
        if (ctx->boot_count < (uint8_t)FLY_BOOT_COUNT_SAT) {
            ctx->boot_count = (uint8_t)(ctx->boot_count + 1u);
        }
        return;
    }

    /* Trắng hoặc hỏng: nạp mặc định, boot_count về 1. */
    fly_nvm_defaults(&cfg);
    ctx->mode = cfg.mode;
    ctx->wake_chan = cfg.wake_chan;
    ctx->wake_period_s = cfg.wake_period_s;
    ctx->wake_in_cfg_s = cfg.wake_in_s;
    ctx->boot_count = 1u;
    if (rc == FLY_EIO) {
        fly_log_push(ctx, FLY_LOG_NVM, 1u);
        fly_fault_latch(ctx, (uint8_t)FLY_FAULT_NVM);
    }
}

fly_ctx_t *fly_init(const fly_hal_t *hal)
{
    fly_ctx_t *ctx;
    uint32_t now;

    if (!hal_valid(hal)) {
        return NULL;
    }
    ctx = (fly_ctx_t *)calloc(1u, sizeof *ctx);
    if (!ctx) {
        return NULL;
    }
    ctx->hal = hal;
    now = hal->millis(FLY_HAL(ctx));
    ctx->boot_ms = now;
    ctx->sys_flags = (uint8_t)(hal->reset_cause(FLY_HAL(ctx)) & 0x0Fu);
    ctx->event_mask = (uint8_t)0x3Fu; /* giá trị reset của EVENT_MASK */

    drive_idle_outputs(ctx);
    load_config(ctx);

    ctx->state = (uint8_t)FLY_ST_OFF;
    ctx->batt_next_ms = now;
    ctx->temp_next_ms = now;
    ctx->wdg_next_ms = now;

    fly_power_init(ctx, now);
    fly_sched_init(ctx, now);
    fly_log_push(ctx, FLY_LOG_BOOT, ctx->boot_count);
    (void)fly_nvm_save(ctx);
    return ctx;
}

void fly_destroy(fly_ctx_t *ctx)
{
    free(ctx);
}

static void pir_detected(fly_ctx_t *ctx, uint32_t now)
{
    if (ctx->pir_detected &&
        (uint32_t)(now - ctx->pir_detect_ms) < (uint32_t)FLY_PIR_GROUP_MS) {
        /* Trong cửa sổ gộp: không tạo sự kiện mới. */
        return;
    }
    ctx->pir_detected = 1u;
    ctx->pir_detect_ms = now;
    fly_events_post(ctx, FLY_EVENT_PIR);
    fly_power_request_wake(ctx, now);
}

static void sample_inputs(fly_ctx_t *ctx, uint32_t now)
{
    const fly_hal_t *hal = ctx->hal;
    void *h = FLY_HAL(ctx);
    int level;

    level = hal->gpio_read(h, FLY_PIN_VBUS) ? 1 : 0;
    if (level != (int)ctx->vbus_present) {
        ctx->vbus_present = (uint8_t)level;
        fly_events_post(ctx, FLY_EVENT_VBUS_CHANGE);
        if (level) {
            fly_power_exit_survival(ctx, now);
        }
    }

    level = hal->gpio_read(h, FLY_PIN_MODEM_STATUS) ? 1 : 0;
    if (level != (int)ctx->modem_status) {
        ctx->modem_status = (uint8_t)level;
        fly_events_post(ctx, FLY_EVENT_MODEM_STATUS);
    }

    /*
     * MODEM_RI: modem kéo RI khi có SMS/cuộc gọi đến (J_B2B chân 21). Chỉ có
     * nghĩa với kênh SMS; với kênh khác thì bỏ qua để nhiễu chân không đánh
     * thức hệ thống. RI là xung của modem nên không debounce như PIR, nhưng
     * port thật phải chốt cạnh bằng EXTI (xem hal/stm32l0/README.md).
     */
    level = hal->gpio_read(h, FLY_PIN_MODEM_RI) ? 1 : 0;
    if (level != (int)ctx->modem_ri) {
        ctx->modem_ri = (uint8_t)level;
        if (level && ctx->wake_chan == (uint8_t)FLY_WAKE_CHAN_SMS) {
            fly_events_post(ctx, FLY_EVENT_WAKE_ALARM);
            fly_power_request_wake(ctx, now);
        }
    }

    /*
     * PIR chỉ được lấy mẫu ở đây. Mức phải giữ ổn định FLY_PIR_DEBOUNCE_MS
     * mới được tính; xung ngắn hơn bị bỏ.
     */
    level = hal->gpio_read(h, FLY_PIN_PIR) ? 1 : 0;
    if (level != (int)ctx->pir_raw) {
        ctx->pir_raw = (uint8_t)level;
        ctx->pir_raw_ms = now;
    } else if (level != (int)ctx->pir_stable &&
               (uint32_t)(now - ctx->pir_raw_ms) >= (uint32_t)FLY_PIR_DEBOUNCE_MS) {
        ctx->pir_stable = (uint8_t)level;
        if (level) {
            pir_detected(ctx, now);
        }
    }
}

void fly_step(fly_ctx_t *ctx)
{
    uint32_t now;

    if (!ctx) {
        return;
    }
    now = fly_now(ctx);
    ctx->steps = (uint32_t)(ctx->steps + 1u);

    /*
     * Watchdog: cho ăn khi đã quá 5 s kể từ lần trước. Không đưa hạn này vào
     * fly_next_timeout_ms() để không phá vòng ngủ dài — xem README.
     */
    if (fly_due(ctx->wdg_next_ms, now)) {
        ctx->hal->wdg_kick(FLY_HAL(ctx));
        ctx->wdg_next_ms = now + FLY_WDG_KICK_MS;
    }

    sample_inputs(ctx, now);
    fly_power_pulse_step(ctx, now);
    fly_battery_step(ctx, now);
    fly_temp_step(ctx, now);
    fly_sched_step(ctx, now);
    fly_sched_chan_step(ctx, now);
    fly_power_step(ctx, now);
    fly_events_irq_update(ctx);
}

static void consider(uint32_t *best, uint32_t value)
{
    if (value < *best) {
        *best = value;
    }
}

uint32_t fly_next_timeout_ms(fly_ctx_t *ctx)
{
    uint32_t now;
    uint32_t best;

    if (!ctx) {
        return 0u;
    }
    now = fly_now(ctx);
    best = fly_battery_next_timeout(ctx, now);
    consider(&best, fly_temp_next_timeout(ctx, now));
    consider(&best, fly_sched_next_timeout(ctx, now));
    consider(&best, fly_sched_chan_next_timeout(ctx, now));
    consider(&best, fly_power_next_timeout(ctx, now));

    if (ctx->pir_raw != ctx->pir_stable) {
        uint32_t due = ctx->pir_raw_ms + FLY_PIR_DEBOUNCE_MS;
        int32_t delta = (int32_t)(due - now);
        consider(&best, (delta <= 0) ? 0u : (uint32_t)delta);
    }
    return best;
}

void fly_run_slice(fly_ctx_t *ctx, uint32_t max_ms)
{
    uint32_t start;
    uint32_t spins = 0u;

    if (!ctx) {
        return;
    }
    if (max_ms == 0u) {
        fly_step(ctx);
        return;
    }
    start = fly_now(ctx);
    for (;;) {
        uint32_t now;
        uint32_t elapsed;
        uint32_t remain;
        uint32_t wait;

        fly_step(ctx);
        now = fly_now(ctx);
        elapsed = now - start;
        if (elapsed >= max_ms) {
            break;
        }
        remain = max_ms - elapsed;
        wait = fly_next_timeout_ms(ctx);
        if (wait == 0u) {
            /* Có việc phải xử lý ngay: lặp lại, nhưng chặn vòng lặp nóng. */
            spins = (uint32_t)(spins + 1u);
            if (spins > 16u) {
                break;
            }
            continue;
        }
        spins = 0u;
        if (wait > remain) {
            wait = remain;
        }
        (void)ctx->hal->enter_stop(FLY_HAL(ctx), wait);
        if (fly_now(ctx) == now) {
            /* HAL không làm thời gian trôi: thoát để không treo. */
            break;
        }
    }
}

int fly_i2c_read(fly_ctx_t *ctx, uint8_t reg, uint8_t *buf, uint8_t len)
{
    uint8_t i;

    if (!ctx || !buf || len == 0u) {
        return FLY_EINVAL;
    }
    /* Kiểm tra toàn dải trước để không đọc dở dang khi có địa chỉ sai. */
    for (i = 0; i < len; i++) {
        if (!fly_reg_find((uint8_t)(reg + i))) {
            return FLY_EIO;
        }
    }
    for (i = 0; i < len; i++) {
        int rc = fly_reg_read(ctx, (uint8_t)(reg + i), &buf[i]);
        if (rc != FLY_OK) {
            return rc;
        }
    }
    return FLY_OK;
}

int fly_i2c_write(fly_ctx_t *ctx, uint8_t reg, const uint8_t *buf, uint8_t len)
{
    uint8_t i;

    if (!ctx || !buf || len == 0u) {
        return FLY_EINVAL;
    }
    for (i = 0; i < len; i++) {
        const fly_reg_desc_t *desc = fly_reg_find((uint8_t)(reg + i));
        if (!desc || desc->access == FLY_ACCESS_RO) {
            return FLY_EIO;
        }
    }
    for (i = 0; i < len; i++) {
        int rc = fly_reg_write(ctx, (uint8_t)(reg + i), buf[i]);
        if (rc != FLY_OK) {
            return rc;
        }
    }
    return FLY_OK;
}
