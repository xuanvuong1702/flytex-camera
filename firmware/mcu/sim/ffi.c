/*
 * ffi.c — cầu nối C cho mô phỏng Python (ctypes).
 *
 * Mỗi handle gói: HAL host + lõi + buffer JSON thống kê. Không có biến toàn
 * cục, nhiều phiên mô phỏng chạy song song được.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../hal/host/hal_host.h"
#include "ffi.h"
#include "flytex/core.h"
#include "flytex/ctx.h"
#include <stddef.h>

typedef struct {
    hal_host_t host;
    fly_ctx_t *core;
    char json[256];
} fsim_t;

static fsim_t *unwrap(void *h)
{
    return (fsim_t *)h;
}

void *fsim_new(void)
{
    fsim_t *f = (fsim_t *)calloc(1u, sizeof *f);

    if (!f) {
        return NULL;
    }
    hal_host_init(&f->host);
    f->core = fly_init(&f->host.hal);
    if (!f->core) {
        free(f);
        return NULL;
    }
    return (void *)f;
}

void fsim_free(void *h)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return;
    }
    fly_destroy(f->core);
    free(f);
}

int fsim_set_input(void *h, int pin, int level)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return FLY_EINVAL;
    }
    return hal_host_set_input(&f->host, pin, level);
}

int fsim_set_adc_mv(void *h, int ch, unsigned mv)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return FLY_EINVAL;
    }
    return hal_host_set_adc_mv(&f->host, ch, (uint32_t)mv);
}

int fsim_set_temp_c(void *h, int sensor, int c)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return FLY_EINVAL;
    }
    return hal_host_set_temp_c(&f->host, sensor, c);
}

void fsim_step(void *h)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return;
    }
    fly_step(f->core);
    hal_host_sync_steps(&f->host, f->core);
}

int fsim_advance_ms(void *h, unsigned ms)
{
    fsim_t *f = unwrap(h);
    uint32_t before;

    if (!f) {
        return 0;
    }
    before = f->host.now_ms;
    fly_run_slice(f->core, (uint32_t)ms);
    hal_host_sync_steps(&f->host, f->core);
    return (int)(uint32_t)(f->host.now_ms - before);
}

int fsim_i2c_read(void *h, int reg, unsigned char *buf, int len)
{
    fsim_t *f = unwrap(h);
    int rc;

    if (!f || !buf || len <= 0 || len > 255 || reg < 0 || reg > 255) {
        return FLY_EINVAL;
    }
    rc = fly_i2c_read(f->core, (uint8_t)reg, (uint8_t *)buf, (uint8_t)len);
    if (rc != FLY_OK) {
        hal_host_note_i2c_nack(&f->host);
    }
    return rc;
}

int fsim_i2c_write(void *h, int reg, const unsigned char *buf, int len)
{
    fsim_t *f = unwrap(h);
    int rc;

    if (!f || !buf || len <= 0 || len > 255 || reg < 0 || reg > 255) {
        return FLY_EINVAL;
    }
    rc = fly_i2c_write(f->core, (uint8_t)reg, (const uint8_t *)buf, (uint8_t)len);
    if (rc != FLY_OK) {
        hal_host_note_i2c_nack(&f->host);
    }
    return rc;
}

int fsim_get_output(void *h, int pin)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return -1;
    }
    return hal_host_get_output(&f->host, pin);
}

const char *fsim_stats_json(void *h)
{
    fsim_t *f = unwrap(h);
    const hal_host_stats_t *s;

    if (!f) {
        return "{}";
    }
    s = &f->host.stats;
    (void)snprintf(f->json, sizeof f->json,
                   "{\"stop_entries\":%lu,\"stop_ms\":%lu,\"wdg_kicks\":%lu,"
                   "\"i2c_nacks\":%lu,\"steps\":%lu}",
                   (unsigned long)s->stop_entries, (unsigned long)s->stop_ms,
                   (unsigned long)s->wdg_kicks, (unsigned long)s->i2c_nacks,
                   (unsigned long)s->steps);
    return f->json;
}

unsigned fsim_now_ms(void *h)
{
    fsim_t *f = unwrap(h);

    if (!f) {
        return 0u;
    }
    return (unsigned)f->host.now_ms;
}
