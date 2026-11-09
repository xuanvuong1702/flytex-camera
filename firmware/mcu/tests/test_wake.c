/*
 * test_wake.c — giới hạn tần suất đánh thức bằng RI (SMS rác).
 */
#include "test.h"

#include "../hal/host/hal_host.h"
#include "flytex/core.h"
#include "flytex/ctx.h"
#include "flytex/regs_gen.h"
#include <stddef.h>

static hal_host_t host;
static fly_ctx_t *core;

static int setup(void)
{
    hal_host_init(&host);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, 25);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, 25);
    core = fly_init(&host.hal);
    if (!core) {
        return 0;
    }
    core->wake_chan = (uint8_t)FLY_WAKE_CHAN_SMS;
    return 1;
}

static void teardown(void)
{
    fly_destroy(core);
    core = NULL;
}

static void ri(int level)
{
    (void)hal_host_set_input(&host, FLY_PIN_MODEM_RI, level);
}

TEST_CASE(test_ri_wake_rate_limited)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    fly_run_slice(core, 5000u);
    core->ri_wake_valid = 1u;
    core->ri_last_wake_ms = 1000u;

    ri(1);
    fly_run_slice(core, 150u);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);
    teardown();
}

TEST_CASE(test_ri_wake_allowed_after_interval)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    fly_run_slice(core, 5000u);
    core->ri_wake_valid = 1u;
    core->ri_last_wake_ms = 0u;
    fly_run_slice(core, 600001u); /* vuot cua so 10 phut */

    ri(1);
    fly_run_slice(core, 150u);
    TEST_ASSERT(hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}
