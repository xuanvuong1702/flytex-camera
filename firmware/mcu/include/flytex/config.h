/*
 * config.h — hằng số cấu hình của lõi MCU giám sát.
 *
 * Đây là chính sách, không phải số đo. Mỗi nhóm ghi nguồn tài liệu; chỗ chưa
 * kiểm chứng trên board thật đánh dấu [CHƯA XÁC MINH] và phải đo lại ở G0.
 * Đơn vị ghi ngay trong tên hằng: _MS mili giây, _S giây, _MV mili vôn, _C độ C.
 */
#ifndef FLYTEX_CONFIG_H
#define FLYTEX_CONFIG_H

/* ------------------------------------------------------------------ */
/* Điện áp pin — docs/14 §3.4, docs/02 §10, docs/10 R-11               */
/* ------------------------------------------------------------------ */

/*
 * Mạch chia áp trên chân ADC là bắt buộc: LFP 1S có thể tới 3,65 V, cao hơn
 * rail 3,3 V. Tỉ lệ 1:2 là điểm khởi đầu [CHƯA XÁC MINH]; sửa hai hằng số
 * này khi chốt giá trị điện trở. adc_mv() trả mV tại chân, lõi nhân tỉ lệ.
 */
#define FLY_BATT_DIV_NUM 2u
#define FLY_BATT_DIV_DEN 1u

/* Ngưỡng có tải, mV. LFP: cảnh báo 3,05 V, cắt 2,90 V, khôi phục 3,20 V.
 * Mọi ngưỡng phải giữ liên tục N mẫu (10 s/mẫu) mới có hiệu lực — xem battery.c. */
#define FLY_BATT_WARN_MV 3050u
#define FLY_BATT_CUTOFF_MV 2900u
#define FLY_BATT_RECOVER_MV 3200u
#define FLY_BATT_WARN_N 6u
#define FLY_BATT_CUTOFF_N 3u
#define FLY_BATT_RECOVER_N 12u

/* Chu kỳ lấy mẫu ADC, ms. */
#define FLY_BATT_SAMPLE_MS 10000u

/* ------------------------------------------------------------------ */
/* Nhiệt độ — docs/14 §3.4, docs/02 §6.3                               */
/* ------------------------------------------------------------------ */

/*
 * Ngưỡng firmware chỉ để BÁO CÁO và cấm sạc; cắt sạc an toàn là việc của
 * phần cứng (docs/02 §6.3), firmware không phải lớp an toàn duy nhất.
 * Hysteresis 2 °C: đặt khi vượt ngưỡng, xóa khi đã qua ngưỡng ngược lại.
 */
#define FLY_TEMP_SAMPLE_MS 10000u
#define FLY_TEMP_HIGH_C 45         /* > 45 °C là quá nóng */
#define FLY_TEMP_HIGH_CLEAR_C 43   /* < 43 °C mới coi là hết nóng */
#define FLY_TEMP_LOW_C 0           /* < 0 °C là quá lạnh */
#define FLY_TEMP_LOW_CLEAR_C 2     /* > 2 °C mới coi là hết lạnh */

/* Byte ghi vào BAT_TEMP_C/AMB_TEMP_C khi không đọc được cảm biến. */
#define FLY_TEMP_INVALID_RAW 0x80u

/* ------------------------------------------------------------------ */
/* Bắt tay nguồn — docs/03 §5, docs/04 §2.3, docs/14 §3.2              */
/* ------------------------------------------------------------------ */

#define FLY_SOC_BOOT_TIMEOUT_MS 20000u  /* chờ SOC_READY sau khi bật rail */
#define FLY_SOC_BOOT_RETRIES 2u         /* số lần thử lại sau lần đầu */
#define FLY_SOC_RETRY_DELAY_MS 500u     /* để rail xả hết trước khi thử lại */
#define FLY_SHUTDOWN_TIMEOUT_MS 10000u  /* chờ CMD SOC_SHUTDOWN_DONE */
#define FLY_SHUTDOWN_CUT_DELAY_MS 500u  /* chờ thêm trước khi cắt rail */

/* ------------------------------------------------------------------ */
/* Watchdog — docs/04 §2.2                                             */
/* ------------------------------------------------------------------ */

/*
 * Khoảng cách tối thiểu giữa hai lần gọi wdg_kick, ms. Watchdog KHÔNG tạo
 * wake: nó không xuất hiện trong fly_next_timeout_ms(). Hệ quả và cách xử lý
 * ở port thật ghi trong hal/stm32l0/README.md.
 */
#define FLY_WDG_KICK_MS 5000u

/* ------------------------------------------------------------------ */
/* PIR — docs/04 §2.1                                                  */
/* ------------------------------------------------------------------ */

#define FLY_PIR_DEBOUNCE_MS 100u  /* mức phải giữ ổn định mới tính */
#define FLY_PIR_GROUP_MS 2000u    /* cửa sổ gộp các lần phát hiện */

/* ------------------------------------------------------------------ */
/* Lịch và kênh đánh thức — spec/registers.toml (WAKE_CHAN, v1.1)      */
/* ------------------------------------------------------------------ */

#define FLY_WAKE_PERIOD_DEFAULT_S 900u    /* khi WAKE_PERIOD_S = 0 */
#define FLY_WAKE_IN_MAX_S (86400u * 20u)  /* trần 20 ngày, tránh tràn ms */
#define FLY_MODEM_READY_TIMEOUT_MS 30000u /* chờ chân STATUS modem */

/* ------------------------------------------------------------------ */
/* Xung điều khiển modem — datasheet EC200U chưa đọc [CHƯA XÁC MINH]   */
/* ------------------------------------------------------------------ */

#define FLY_MODEM_RESET_PULSE_MS 200u
#define FLY_MODEM_PWRKEY_PULSE_MS 500u
/*
 * Mức tích cực của hai xung. EC200U dùng RESET_N và PWRKEY tích cực mức thấp
 * theo họ module Quectel, nhưng phải đọc datasheet của đúng breakout trước
 * khi hàn [CHƯA XÁC MINH].
 */
#define FLY_MODEM_RESET_ACTIVE_LEVEL 0
#define FLY_MODEM_PWRKEY_ACTIVE_LEVEL 0

/* ------------------------------------------------------------------ */
/* Mức logic — phần cứng chưa chốt [CHƯA XÁC MINH]                     */
/* ------------------------------------------------------------------ */

#define FLY_RAIL_ON_LEVEL 1
#define FLY_IRQ_ASSERT_LEVEL 0        /* MCU_IRQ mức thấp là có sự kiện */
#define FLY_CHG_INHIBIT_LEVEL 1       /* mức cấm sạc tới chân charger */

/* ------------------------------------------------------------------ */
/* Bão hòa thanh ghi — spec/registers.toml                             */
/* ------------------------------------------------------------------ */

#define FLY_UPTIME_SAT_S 65535u
#define FLY_BOOT_COUNT_SAT 255u

/* Kích thước ảnh NVM và phiên bản bố cục (xem nvm.h). */
#define FLY_NVM_VERSION 1u
#define FLY_NVM_IMAGE_SIZE 16u

#endif /* FLYTEX_CONFIG_H */
