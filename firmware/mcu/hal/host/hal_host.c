/*
 * hal_host.c — HAL giả: thời gian mô phỏng, chân đọc/ghi được, NVM trong RAM.
 */
#include <string.h>

#include "hal_host.h"
#include "flytex/core.h"
#include "flytex/ctx.h"
#include "flytex/regs_gen.h"
#include <stddef.h>

/* ctx của mọi hàm HAL là &h->hal; hal là field đầu tiên nên trả về h. */
static hal_host_t *self(void *ctx)
{
    return (hal_host_t *)ctx;
}

static uint32_t host_millis(void *ctx)
{
    return self(ctx)->now_ms;
}

static uint32_t host_enter_stop(void *ctx, uint32_t max_ms)
{
    hal_host_t *h = self(ctx);
    uint32_t mask = 0u;

    h->stats.stop_entries = (uint32_t)(h->stats.stop_entries + 1u);
    h->stats.stop_ms = (uint32_t)(h->stats.stop_ms + max_ms);
    h->now_ms = (uint32_t)(h->now_ms + max_ms);

    if (h->input_level[FLY_PIN_PIR]) {
        mask |= FLY_WAKE_PIR;
    }
    if (h->input_level[FLY_PIN_VBUS]) {
        mask |= FLY_WAKE_VBUS;
    }
    if (h->input_level[FLY_PIN_MODEM_STATUS]) {
        mask |= FLY_WAKE_MODEM_STATUS;
    }
    if (max_ms != UINT32_MAX) {
        mask |= FLY_WAKE_RTC;
    }
    return mask;
}

static int host_gpio_read(void *ctx, int pin)
{
    hal_host_t *h = self(ctx);

    if (pin < 0 || pin >= FLY_PIN_COUNT) {
        return 0;
    }
    if (fly_pin_is_input(pin)) {
        return h->input_level[pin] ? 1 : 0;
    }
    if (fly_pin_is_output(pin)) {
        return h->output_level[pin] ? 1 : 0;
    }
    return 0;
}

static void host_delay_us(void *ctx, uint32_t us)
{
    (void)ctx;
    (void)us; /* host không cần thời gian thực; test đếm cạnh */
}

static void host_gpio_write(void *ctx, int pin, int level)
{
    hal_host_t *h = self(ctx);

    if (pin < 0 || pin >= FLY_PIN_COUNT) {
        return;
    }
    if (fly_pin_is_output(pin)) {
        if (pin == FLY_PIN_CHG_INHIBIT && level && !h->output_level[pin]) {
            h->chg_pulses++;
        }
        h->output_level[pin] = level ? 1 : 0;
    }
}

static int host_adc_mv(void *ctx, int ch, uint32_t *mv)
{
    hal_host_t *h = self(ctx);

    if (!mv || ch < 0 || ch >= FLY_ADC_CHANNELS) {
        return FLY_EINVAL;
    }
    *mv = h->adc_mv[ch];
    return FLY_OK;
}

static int host_temp_c(void *ctx, int sensor, int8_t *c)
{
    hal_host_t *h = self(ctx);

    if (!c || sensor < 0 || sensor >= FLY_TEMP_SENSORS) {
        return FLY_EINVAL;
    }
    if (h->temp_c[sensor] <= (int16_t)FLY_TEMP_INVALID) {
        return FLY_ENOSYS;
    }
    *c = (int8_t)h->temp_c[sensor];
    return FLY_OK;
}

static int host_nvm_read(void *ctx, uint32_t off, void *buf, uint32_t len)
{
    hal_host_t *h = self(ctx);

    if (!buf || off > FLY_HOST_NVM_SIZE || len > (FLY_HOST_NVM_SIZE - off)) {
        return FLY_EINVAL;
    }
    memcpy(buf, &h->nvm[off], len);
    return FLY_OK;
}

static int host_nvm_write(void *ctx, uint32_t off, const void *buf, uint32_t len)
{
    hal_host_t *h = self(ctx);

    if (!buf || off > FLY_HOST_NVM_SIZE || len > (FLY_HOST_NVM_SIZE - off)) {
        return FLY_EINVAL;
    }
    memcpy(&h->nvm[off], buf, len);
    return FLY_OK;
}

static void host_wdg_kick(void *ctx)
{
    hal_host_t *h = self(ctx);

    h->stats.wdg_kicks = (uint32_t)(h->stats.wdg_kicks + 1u);
}

static uint64_t host_epoch_s(void *ctx)
{
    hal_host_t *h = self(ctx);

    return h->epoch_base_s + (uint64_t)(h->now_ms / 1000u);
}

static uint8_t host_reset_cause(void *ctx)
{
    return self(ctx)->reset_flags;
}

void hal_host_init(hal_host_t *h)
{
    uint32_t i;

    if (!h) {
        return;
    }
    memset(h, 0, sizeof *h);

    h->hal.millis = host_millis;
    h->hal.enter_stop = host_enter_stop;
    h->hal.gpio_read = host_gpio_read;
    h->hal.gpio_write = host_gpio_write;
    h->hal.delay_us = host_delay_us;
    h->hal.adc_mv = host_adc_mv;
    h->hal.temp_c = host_temp_c;
    h->hal.nvm_read = host_nvm_read;
    h->hal.nvm_write = host_nvm_write;
    h->hal.wdg_kick = host_wdg_kick;
    h->hal.epoch_s = host_epoch_s;
    h->hal.reset_cause = host_reset_cause;

    h->now_ms = 0u;
    h->epoch_base_s = 1700000000ull;
    h->reset_flags = (uint8_t)FLY_SYS_FLAGS_POR_BOR;

    for (i = 0; i < FLY_PIN_COUNT; i++) {
        h->input_level[i] = 0;
        h->output_level[i] = 0;
    }
    for (i = 0; i < FLY_ADC_CHANNELS; i++) {
        h->adc_mv[i] = 0u;
    }
    /* Giá trị bench: 1650 mV tại chân → 3300 mV pin với hệ số chia 1:2. */
    h->adc_mv[FLY_ADC_VBAT] = 1650u;
    for (i = 0; i < FLY_TEMP_SENSORS; i++) {
        h->temp_c[i] = (int16_t)FLY_TEMP_INVALID;
    }
    memset(h->nvm, 0xFF, sizeof h->nvm);
}

void hal_host_reset(hal_host_t *h)
{
    hal_host_init(h);
}

void hal_host_clear_stats(hal_host_t *h)
{
    if (!h) {
        return;
    }
    memset(&h->stats, 0, sizeof h->stats);
}

int hal_host_set_input(hal_host_t *h, int pin, int level)
{
    if (!h || !fly_pin_is_input(pin)) {
        return FLY_EINVAL;
    }
    h->input_level[pin] = level ? 1 : 0;
    return FLY_OK;
}

int hal_host_get_input(const hal_host_t *h, int pin)
{
    if (!h || !fly_pin_is_input(pin)) {
        return -1;
    }
    return h->input_level[pin] ? 1 : 0;
}

int hal_host_get_output(const hal_host_t *h, int pin)
{
    if (!h || !fly_pin_is_output(pin)) {
        return -1;
    }
    return h->output_level[pin] ? 1 : 0;
}

uint32_t hal_host_get_chg_pulses(const hal_host_t *h)
{
    return h ? h->chg_pulses : 0u;
}

int hal_host_set_adc_mv(hal_host_t *h, int ch, uint32_t mv)
{
    if (!h || ch < 0 || ch >= FLY_ADC_CHANNELS) {
        return FLY_EINVAL;
    }
    h->adc_mv[ch] = mv;
    return FLY_OK;
}

int hal_host_set_temp_c(hal_host_t *h, int sensor, int celsius)
{
    if (!h || sensor < 0 || sensor >= FLY_TEMP_SENSORS) {
        return FLY_EINVAL;
    }
    if (celsius < -128) {
        celsius = -128;
    }
    if (celsius > 127) {
        celsius = 127;
    }
    h->temp_c[sensor] = (int16_t)celsius;
    return FLY_OK;
}

void hal_host_set_reset_cause(hal_host_t *h, uint8_t flags)
{
    if (h) {
        h->reset_flags = flags;
    }
}

const hal_host_stats_t *hal_host_stats(const hal_host_t *h)
{
    return h ? &h->stats : NULL;
}

void hal_host_sync_steps(hal_host_t *h, const struct fly_ctx *ctx)
{
    if (!h) {
        return;
    }
    h->stats.steps = ctx ? (uint32_t)ctx->steps : 0u;
}

void hal_host_note_i2c_nack(hal_host_t *h)
{
    if (h) {
        h->stats.i2c_nacks = (uint32_t)(h->stats.i2c_nacks + 1u);
    }
}
