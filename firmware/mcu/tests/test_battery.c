/*
 * test_battery.c — hệ số chia áp, lọc, ngưỡng LFP có đếm mẫu, LOW_BATT.
 */
#include "test.h"

#include "../hal/host/hal_host.h"
#include "flytex/battery.h"
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

/* Nạp N mẫu liền nhau (không tua thời gian) để kiểm đếm mẫu và bộ lọc. */
static void feed(uint16_t mv, int n)
{
    int i;

    set_vbat(mv);
    for (i = 0; i < n; i++) {
        fly_battery_force(core, 0u);
    }
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
    set_vbat(3300u);
    fly_step(core);
    TEST_ASSERT_EQ(3300, t_rd16_be(core, FLY_REG_VBAT_MV));

    set_vbat(2000u);
    fly_run_slice(core, FLY_BATT_SAMPLE_MS);
    TEST_ASSERT_EQ(2000, t_rd16_be(core, FLY_REG_VBAT_MV));
    teardown();
}

TEST_CASE(test_warn_needs_persistence)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    feed(3048u, 1);
    TEST_ASSERT_EQ(0, low_batt_bit()); /* một mẫu chưa đủ */

    feed(3048u, (int)FLY_BATT_WARN_N - 1);
    TEST_ASSERT_EQ(1, low_batt_bit());

    /* Trên ngưỡng cảnh báo nhưng dưới ngưỡng khôi phục: giữ nguyên. */
    feed(3150u, 5);
    TEST_ASSERT_EQ(1, low_batt_bit());

    /* Khôi phục cần đủ số mẫu liên tiếp. */
    feed(3300u, (int)FLY_BATT_RECOVER_N + 20);
    TEST_ASSERT_EQ(0, low_batt_bit());
    teardown();
}

TEST_CASE(test_low_batt_event_once_per_crossing)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    feed(3048u, (int)FLY_BATT_WARN_N);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);

    /* Vẫn thấp: không được tạo sự kiện mới. */
    feed(3048u, 6);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);

    /* Hồi phục rồi lại tụt: sự kiện mới. */
    feed(3300u, (int)FLY_BATT_RECOVER_N + 20);
    TEST_ASSERT_EQ(0, low_batt_bit());
    feed(3048u, 80); /* bộ lọc cần thời gian hội tụ từ 3,3 V xuống */
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_LOW_BATT);
    teardown();
}

TEST_CASE(test_cutoff_needs_three_samples)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    feed(2898u, (int)FLY_BATT_CUTOFF_N - 1);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);

    feed(2898u, 1);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT_EQ(FLY_FAULT_BATT_UNDERVOLTAGE, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_cutoff_transient_does_not_latch)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    feed(2898u, 2);
    feed(3300u, 1); /* sụt áp thoáng qua, quay lại bình thường */
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT_EQ(0, low_batt_bit());
    teardown();
}

TEST_CASE(test_no_sampling_in_survival)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    feed(2898u, (int)FLY_BATT_CUTOFF_N);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);

    set_vbat(3300u);
    fly_run_slice(core, FLY_BATT_SAMPLE_MS);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    teardown();
}
