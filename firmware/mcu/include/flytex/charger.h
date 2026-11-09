#ifndef FLYTEX_CHARGER_H
#define FLYTEX_CHARGER_H

#include "flytex/ctx.h"

/* Gửi chuỗi xung cấu hình dòng sạc BQ25070 trên chân CHG_CTRL. */
void fly_charger_program(fly_ctx_t *ctx, int pulses);

#endif
