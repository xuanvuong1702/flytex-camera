/*
 * test_charger.c — chuỗi 11 xung cấu hình dòng sạc BQ25070.
 */
#include "test.h"

#include "../hal/host/hal_host.h"
#include "flytex/charger.h"
#include "flytex/core.h"
#include <stddef.h>

static hal_host_t host;
static fly_ctx_t *core;

static int setup(void)
{
    hal_host_init(&host);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, 25);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, 25);
    core = fly_init(&host.hal);
    return core != NULL;
}

static void teardown(void)
{
    fly_destroy(core);
    core = NULL;
}

TEST_CASE(test_charger_programmed_at_boot)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* fly_init phải phát đúng 11 xung; CTRL kết thúc ở mức thấp (enable). */
    TEST_ASSERT_EQ(11, hal_host_get_chg_pulses(&host));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_CHG_INHIBIT));

    /* Gọi lại với số xung khác: chỉ để kiểm hàm, không cấu hình sai. */
    fly_charger_program(core, 10);
    TEST_ASSERT_EQ(21, hal_host_get_chg_pulses(&host));
    teardown();
}

TEST_CASE(test_charger_zero_pulses_is_noop)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    fly_charger_program(core, 0);
    TEST_ASSERT_EQ(11, hal_host_get_chg_pulses(&host));
    teardown();
}
