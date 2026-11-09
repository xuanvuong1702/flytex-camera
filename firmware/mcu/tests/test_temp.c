/*
 * test_temp.c — nhiệt độ pin/môi trường, ngưỡng, hysteresis, cảm biến thiếu.
 *
 * Test "cảm biến thiếu" phải thất bại nếu ai đó trả 25 °C thay cho 0x80.
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

static void set_batt_temp(int celsius)
{
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, celsius);
}

TEST_CASE(test_temperature_in_range)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_batt_temp(25);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, 30);
    fly_step(core);
    TEST_ASSERT_EQ(25u, t_rd(core, FLY_REG_BAT_TEMP_C));
    TEST_ASSERT_EQ(30u, t_rd(core, FLY_REG_AMB_TEMP_C));
    TEST_ASSERT_EQ(FLY_FAULT_NONE, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_CHG) & FLY_CHG_CHARGE_INHIBIT);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_CHG_INHIBIT));
    teardown();
}

TEST_CASE(test_overtemp_fault_and_inhibit)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_batt_temp(50);
    fly_step(core);
    TEST_ASSERT_EQ(50u, t_rd(core, FLY_REG_BAT_TEMP_C));
    TEST_ASSERT_EQ(FLY_FAULT_BATT_OVERTEMP, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT(t_rd(core, FLY_REG_CHG) & FLY_CHG_CHARGE_INHIBIT);
    TEST_ASSERT(t_rd(core, FLY_REG_SYS_FLAGS) & FLY_SYS_FLAGS_CHG_INHIBIT);
    TEST_ASSERT_EQ(FLY_CHG_INHIBIT_LEVEL, hal_host_get_output(&host, FLY_PIN_CHG_INHIBIT));
    teardown();
}

TEST_CASE(test_overtemp_hysteresis)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_batt_temp(50);
    fly_step(core);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_OVERTEMP, t_rd(core, FLY_REG_FAULT_CODE));

    set_batt_temp(44); /* vẫn trên mức xóa 43 */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_OVERTEMP, t_rd(core, FLY_REG_FAULT_CODE));

    set_batt_temp(42); /* dưới 43: hết quá nóng */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(FLY_FAULT_NONE, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_CHG) & FLY_CHG_CHARGE_INHIBIT);

    set_batt_temp(46); /* vượt 45: quá nóng lại */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_OVERTEMP, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_undertemp_fault_and_hysteresis)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_batt_temp(-5);
    fly_step(core);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_UNDERTEMP, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT(t_rd(core, FLY_REG_CHG) & FLY_CHG_CHARGE_INHIBIT);

    set_batt_temp(1); /* vẫn dưới mức xóa 2 */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_UNDERTEMP, t_rd(core, FLY_REG_FAULT_CODE));

    set_batt_temp(3);
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(FLY_FAULT_NONE, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_missing_battery_sensor_is_invalid_not_25)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* -128 = HAL không có cảm biến. */
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, -128);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, 25);
    fly_step(core);

    TEST_ASSERT_EQ(0x80u, t_rd(core, FLY_REG_BAT_TEMP_C));
    /* Khẳng định rõ: không được là 25 (0x19). */
    TEST_ASSERT(t_rd(core, FLY_REG_BAT_TEMP_C) != 25);
    TEST_ASSERT_EQ(FLY_FAULT_SENSOR_STALE, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_missing_ambient_sensor_is_invalid)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, 20);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, -128);
    fly_step(core);
    TEST_ASSERT_EQ(0x80u, t_rd(core, FLY_REG_AMB_TEMP_C));
    TEST_ASSERT_EQ(20u, t_rd(core, FLY_REG_BAT_TEMP_C));
    TEST_ASSERT_EQ(FLY_FAULT_SENSOR_STALE, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}
