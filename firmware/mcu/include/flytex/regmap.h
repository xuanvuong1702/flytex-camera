/*
 * regmap.h — đọc/ghi một byte thanh ghi theo bảng sinh fly_reg_descs.
 *
 * Quy tắc (spec/registers.toml):
 *   - địa chỉ ngoài dải hoặc không định nghĩa → NACK (FLY_EIO);
 *   - ghi thanh ghi chỉ đọc, đọc thanh ghi chỉ ghi → NACK;
 *   - nhóm nhiều byte big-endian: đọc byte cao chốt cả nhóm, ghi byte cuối
 *     mới commit;
 *   - EVENT xóa khi đọc;
 *   - CMD lạ: đặt FAULT_CODE = BAD_CMD và không làm gì.
 *
 * fly_i2c_read/fly_i2c_write trong core.c dùng các hàm dưới đây cho từng byte.
 */
#ifndef FLYTEX_REGMAP_H
#define FLYTEX_REGMAP_H

#include <stdint.h>

#include "flytex/regs_gen.h"
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

struct fly_ctx;

/* Đọc một byte thanh ghi tại địa chỉ addr. Trả FLY_OK hoặc FLY_EIO. */
int fly_reg_read(struct fly_ctx *ctx, uint8_t addr, uint8_t *out);

/*
 * Ghi một byte thanh ghi. Trả FLY_OK, FLY_EIO (NACK) hoặc FLY_EINVAL (giá trị
 * không hợp lệ với MODE/WAKE_CHAN).
 */
int fly_reg_write(struct fly_ctx *ctx, uint8_t addr, uint8_t value);

/* Tra bảng mô tả; NULL nếu địa chỉ không được định nghĩa. */
const fly_reg_desc_t *fly_reg_find(uint8_t addr);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_REGMAP_H */
