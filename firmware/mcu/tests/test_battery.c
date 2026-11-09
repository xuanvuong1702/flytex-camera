/*
 * test_battery.c — hệ số chia áp, ngưỡng cảnh báo/tắt/khôi phục, LOW_BATT.
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

/* Đặt mV tại chân ADC để ra đúng mV pin sau hệ số chia 2. */
static void set_vbat(uint16_t mv)
{
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, (uint32_t)mv / FLY_BATT_DIV_NUM);
}

static int low_batt_bit(void)
{
    return (t_rd(core, FLY_REG_STATUS) & FLY_STATUS_LOW_BATT) ? 1 : 0;
}

TEST_CASE(test_divider_scaling)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* 1650 mV tại chân × 2 = 3300 mV pin. */
    set_vbat(3300u);
    fly_step(core);
    TEST_ASSERT_EQ(3300, t_rd16_be(core, FLY_REG_VBAT_MV));

    /* 1000 mV tại chân × 2 = 2000 mV pin, sau kỳ lấy mẫu kế tiếp. */
    set_vbat(2000u);
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(2000, t_rd16_be(core, FLY_REG_VBAT_MV));
    teardown();
}

TEST_CASE(test_warn_threshold_with_hysteresis)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_vbat(3100u); /* đúng ngưỡng: chưa cảnh báo */
    fly_step(core);
    TEST_ASSERT_EQ(0, low_batt_bit());

    set_vbat(3098u); /* dưới ngưỡng */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(1, low_batt_bit());

    set_vbat(3150u); /* trên ngưỡng nhưng dưới mức khôi phục */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(1, low_batt_bit());

    set_vbat(3298u); /* vẫn dưới 3300 */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(1, low_batt_bit());

    set_vbat(3300u); /* chạm mức khôi phục */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(0, low_batt_bit());
    teardown();
}

TEST_CASE(test_low_batt_event_once_per_crossing)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_vbat(3098u);
    fly_step(core);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);

    /* Vẫn thấp: không được tạo sự kiện mới. */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);

    /* Hồi phục rồi lại tụt: sự kiện mới. */
    set_vbat(3300u);
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(0, low_batt_bit());
    set_vbat(3098u);
    fly_run_slice(core, 10000u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);
    teardown();
}

TEST_CASE(test_cutoff_enters_survival)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_vbat(2898u);
    fly_step(core);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_UNDERVOLTAGE, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_no_sampling_in_survival)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    set_vbat(2898u);
    fly_step(core);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);

    /* Pin hồi phục nhưng đang sinh tồn: chỉ VBUS mới đánh thức, không lấy mẫu. */
    set_vbat(3300u);
    fly_run_slice(core, 10000u);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    teardown();
}
