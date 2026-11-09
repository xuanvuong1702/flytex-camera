/*
 * test_pir.c — debounce và cửa sổ gộp của PIR.
 *
 * PIR chỉ được lấy mẫu trong fly_step, nên mọi thay đổi mức chân chỉ có hiệu
 * lực sau khi thời gian mô phỏng trôi qua một bước.
 */
#include "test.h"

#include "../hal/host/hal_host.h"
#include "flytex/core.h"
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
    return core != NULL;
}

static void teardown(void)
{
    fly_destroy(core);
    core = NULL;
}

static void advance(uint32_t ms)
{
    fly_run_slice(core, ms);
}

static void pir(int level)
{
    (void)hal_host_set_input(&host, FLY_PIN_PIR, level);
}

TEST_CASE(test_short_pulse_rejected)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* Xung 50 ms, ngắn hơn debounce 100 ms. */
    pir(1);
    advance(50u);
    pir(0);
    advance(200u);

    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_long_pulse_detected)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    pir(1);
    advance(150u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_two_pulses_merged)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* Xung thứ nhất: phát hiện. */
    pir(1);
    advance(150u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    pir(0);
    advance(100u);

    /* Xung thứ hai trong cửa sổ 2 s: gộp, không có sự kiện mới. */
    pir(1);
    advance(150u);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    pir(0);
    advance(2500u);

    /* Xung thứ ba sau cửa sổ gộp: sự kiện mới. */
    pir(1);
    advance(150u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    teardown();
}

TEST_CASE(test_not_sampled_outside_step)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* Đổi mức chân nhưng chưa gọi fly_step: chưa có gì xảy ra. */
    pir(1);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));

    fly_step(core);
    /* Mới một bước, chưa đủ debounce. */
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    teardown();
}
