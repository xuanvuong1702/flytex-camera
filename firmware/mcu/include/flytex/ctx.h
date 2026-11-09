/*
 * ctx.h — trạng thái nội bộ của lõi.
 *
 * KHÔNG phải API công khai cho ứng dụng. Chỉ các module trong src/, HAL host
 * và lớp FFI được include file này; toàn bộ trạng thái nằm trong một struct
 * do fly_init() cấp phát.
 */
#ifndef FLYTEX_CTX_H
#define FLYTEX_CTX_H

#include <stdint.h>

#include "flytex/config.h"
#include "flytex/core.h"
#include "flytex/hal.h"
#include "flytex/log.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Máy trạng thái nguồn phía MCU. */
enum fly_state {
    FLY_ST_OFF = 0,    /* SoC và modem tắt theo cấu hình */
    FLY_ST_BOOT,       /* đã bật +5V_SOC, chờ SOC_READY */
    FLY_ST_ON,         /* SoC đang chạy */
    FLY_ST_SHUTDOWN,   /* đã đặt SHUTDOWN_REQ, chờ SOC_SHUTDOWN_DONE */
    FLY_ST_RETRY,      /* rail vừa cắt, chờ thử lại */
    FLY_ST_SURVIVAL    /* sinh tồn: chỉ thức khi có VBUS */
};

struct fly_ctx {
    const fly_hal_t *hal;

    /* ---- thời gian ---- */
    uint32_t boot_ms;
    uint32_t steps;
    uint32_t wdg_next_ms;
    uint32_t batt_next_ms;
    uint32_t temp_next_ms;

    /* ---- cấu hình đọc từ NVM ---- */
    uint8_t mode;          /* FLY_MODE_ECO / FLY_MODE_WATCH */
    uint8_t wake_chan;     /* FLY_WAKE_CHAN_* */
    uint16_t wake_period_s;/* 0 = dùng mặc định */
    uint32_t wake_in_cfg_s;/* giá trị đã ghi, dùng khi lưu NVM */
    uint8_t boot_count;

    /* ---- máy trạng thái nguồn ---- */
    uint8_t state;
    uint8_t soc_pwr_on;
    uint8_t modem_pwr_on;
    uint8_t soc_ready;
    uint8_t boot_attempts;
    uint8_t boot_armed;
    uint32_t boot_due_ms;
    uint8_t retry_armed;
    uint32_t retry_due_ms;
    uint8_t shutdown_armed;
    uint32_t shutdown_due_ms;
    uint8_t shutdown_kill_modem;
    uint8_t cut_armed;
    uint32_t cut_due_ms;

    /* ---- đầu vào ---- */
    uint8_t vbus_present;
    uint8_t modem_status;
    uint8_t modem_ri; /* mức RI đã lấy mẫu, để phát hiện cạnh lên */
    uint8_t low_batt;

    /* ---- sự kiện, lỗi, IRQ ---- */
    uint8_t event;
    uint8_t event_mask;
    uint8_t fault_latched;
    uint8_t fault_active_temp;
    uint8_t fault_active_batt;
    uint8_t sys_flags;
    uint8_t irq_level;

    /* ---- xung chân (MODEM_RESET, MODEM_PWRKEY) ---- */
    uint8_t pulse_armed;
    uint32_t pulse_due_ms;
    uint8_t pulse_pin;

    /* ---- PIR ---- */
    uint8_t pir_raw;
    uint8_t pir_stable;
    uint32_t pir_raw_ms;
    uint32_t pir_detect_ms;
    uint8_t pir_detected;

    /* ---- pin ---- */
    uint8_t vbat_valid;
    uint16_t vbat_mv;
    uint16_t vbat_latch;
    uint8_t vbat_latched;

    /* ---- nhiệt ---- */
    int8_t batt_temp_c;
    uint8_t batt_temp_valid;
    int8_t amb_temp_c;
    uint8_t amb_temp_valid;
    uint8_t over_temp;
    uint8_t under_temp;
    uint8_t charge_inhibit;

    /* ---- thanh ghi đọc chốt ---- */
    uint16_t uptime_latch;
    uint8_t uptime_latched;
    uint32_t wake_in_latch_s;
    uint8_t wake_in_latched;

    /* ---- lịch ---- */
    uint8_t wake_in_armed;
    uint32_t wake_in_due_ms;

    /* ---- kênh đánh thức ---- */
    uint8_t chan_armed;
    uint32_t chan_due_ms;
    uint8_t chan_wait_ready;
    uint32_t chan_ready_due_ms;

    /* ---- vùng đệm ghi nhiều byte (commit ở byte cuối) ---- */
    uint8_t wake_in_stage[4];
    uint8_t wake_in_stage_mask;
    uint8_t wake_period_stage[2];
    uint8_t wake_period_stage_mask;

    /* ---- log vòng ---- */
    fly_log_entry_t log[FLY_LOG_CAP];
    uint8_t log_head;
    uint8_t log_count;
    uint16_t log_seq;
};

/* Con trỏ "ctx" truyền cho mọi hàm HAL: chính bảng HAL. */
#define FLY_HAL(c) ((void *)(uintptr_t)((c)->hal))

/* Đồng hồ hiện tại của lõi. */
static inline uint32_t fly_now(const fly_ctx_t *ctx)
{
    return ctx->hal->millis(FLY_HAL(ctx));
}

/* So sánh hạn chót kiểu tràn-safe: trả 1 nếu now đã tới due. */
static inline int fly_due(uint32_t due, uint32_t now)
{
    return (int32_t)(now - due) >= 0;
}

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_CTX_H */
