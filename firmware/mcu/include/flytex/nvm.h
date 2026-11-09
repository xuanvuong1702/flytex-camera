/*
 * nvm.h — ảnh cấu hình bền trong NVM.
 *
 * Bố cục 16 byte, little-endian cho trường nhiều byte:
 *   [0]      version (FLY_NVM_VERSION)
 *   [1]      mode
 *   [2]      wake_chan
 *   [3]      boot_count
 *   [4..7]   wake_in_s        uint32
 *   [8..9]   wake_period_s    uint16
 *   [10..11] dự phòng, ghi 0
 *   [12..15] crc32 (IEEE) của 12 byte đầu, uint32
 *
 * Hỏng CRC hoặc sai version → nạp mặc định, FAULT_CODE = NVM, boot_count = 1.
 * NVM trắng (toàn 0xFF) là máy mới xuất xưởng: nạp mặc định, KHÔNG đặt lỗi.
 */
#ifndef FLYTEX_NVM_H
#define FLYTEX_NVM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

typedef struct {
    uint8_t mode;
    uint8_t wake_chan;
    uint8_t boot_count;
    uint32_t wake_in_s;
    uint16_t wake_period_s;
} fly_nvm_cfg_t;

/* Giá trị mặc định khi NVM trắng hoặc hỏng. */
void fly_nvm_defaults(fly_nvm_cfg_t *cfg);

/*
 * Đọc và kiểm tra ảnh NVM.
 * Trả FLY_OK nếu hợp lệ, FLY_ENOSYS nếu NVM trắng, FLY_EIO nếu hỏng.
 * Khi trả khác FLY_OK, cfg đã được điền giá trị mặc định.
 */
int fly_nvm_load(struct fly_ctx *ctx, fly_nvm_cfg_t *cfg);

/* Ghi ảnh NVM từ trạng thái hiện tại. Trả FLY_OK hoặc FLY_EIO. */
int fly_nvm_save(struct fly_ctx *ctx);

/* CRC32 IEEE 802.3, dùng cho ảnh NVM và cho test. */
uint32_t fly_crc32(const uint8_t *data, uint32_t len);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_NVM_H */
