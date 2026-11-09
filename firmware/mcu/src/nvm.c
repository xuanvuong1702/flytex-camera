/*
 * nvm.c — ảnh cấu hình bền: version + crc32, little-endian.
 */
#include <string.h>

#include "flytex/ctx.h"
#include "flytex/events.h"
#include "flytex/nvm.h"
#include "flytex/regs_gen.h"

#define FLY_NVM_CRC_LEN 12u

static void put_u16le(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static uint16_t get_u16le(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}

static void put_u32le(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static uint32_t get_u32le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

uint32_t fly_crc32(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t i;
    int bit;

    if (!data) {
        return 0;
    }
    for (i = 0; i < len; i++) {
        crc ^= (uint32_t)data[i];
        for (bit = 0; bit < 8; bit++) {
            if ((crc & 1u) != 0u) {
                crc = (crc >> 1) ^ 0xEDB88320u;
            } else {
                crc >>= 1;
            }
        }
    }
    return ~crc;
}

void fly_nvm_defaults(fly_nvm_cfg_t *cfg)
{
    if (!cfg) {
        return;
    }
    cfg->mode = (uint8_t)FLY_MODE_ECO;
    cfg->wake_chan = (uint8_t)FLY_WAKE_CHAN_OFF;
    cfg->boot_count = 1u;
    cfg->wake_in_s = 0u;
    cfg->wake_period_s = 0u;
}

int fly_nvm_load(fly_ctx_t *ctx, fly_nvm_cfg_t *cfg)
{
    uint8_t img[FLY_NVM_IMAGE_SIZE];
    uint32_t i;
    uint32_t crc_stored;
    uint32_t crc_calc;
    int all_erased = 1;
    int rc;

    if (!ctx || !cfg) {
        return FLY_EINVAL;
    }
    fly_nvm_defaults(cfg);

    rc = ctx->hal->nvm_read(FLY_HAL(ctx), 0u, img, FLY_NVM_IMAGE_SIZE);
    if (rc != FLY_OK) {
        return FLY_EIO;
    }
    for (i = 0; i < FLY_NVM_IMAGE_SIZE; i++) {
        if (img[i] != 0xFFu) {
            all_erased = 0;
            break;
        }
    }
    if (all_erased) {
        /* Máy mới: NVM chưa từng ghi. Không phải lỗi. */
        return FLY_ENOSYS;
    }
    if (img[0] != (uint8_t)FLY_NVM_VERSION) {
        return FLY_EIO;
    }
    crc_stored = get_u32le(&img[12]);
    crc_calc = fly_crc32(img, FLY_NVM_CRC_LEN);
    if (crc_stored != crc_calc) {
        return FLY_EIO;
    }

    cfg->mode = img[1];
    cfg->wake_chan = img[2];
    cfg->boot_count = img[3];
    cfg->wake_in_s = get_u32le(&img[4]);
    cfg->wake_period_s = get_u16le(&img[8]);

    if (cfg->mode > (uint8_t)FLY_MODE_WATCH || cfg->wake_chan > (uint8_t)FLY_WAKE_CHAN_EDRX_MQTT) {
        fly_nvm_defaults(cfg);
        return FLY_EIO;
    }
    return FLY_OK;
}

int fly_nvm_save(fly_ctx_t *ctx)
{
    uint8_t img[FLY_NVM_IMAGE_SIZE];
    uint32_t crc;
    int rc;

    if (!ctx) {
        return FLY_EINVAL;
    }
    memset(img, 0, sizeof img);
    img[0] = (uint8_t)FLY_NVM_VERSION;
    img[1] = ctx->mode;
    img[2] = ctx->wake_chan;
    img[3] = ctx->boot_count;
    put_u32le(&img[4], ctx->wake_in_cfg_s);
    put_u16le(&img[8], ctx->wake_period_s);
    crc = fly_crc32(img, FLY_NVM_CRC_LEN);
    put_u32le(&img[12], crc);

    rc = ctx->hal->nvm_write(FLY_HAL(ctx), 0u, img, FLY_NVM_IMAGE_SIZE);
    if (rc != FLY_OK) {
        fly_log_push(ctx, FLY_LOG_NVM, 1u);
        fly_fault_latch(ctx, FLY_FAULT_NVM);
        return FLY_EIO;
    }
    return FLY_OK;
}
