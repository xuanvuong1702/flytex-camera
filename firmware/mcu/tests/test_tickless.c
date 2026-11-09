/*
 * test_tickless.c — không có tick 1 ms, ngủ dài, watchdog.
 *
 * Kịch bản 24 giờ không sự kiện chạy ở chế độ sinh tồn: đó là trạng thái duy
 * nhất mà lõi không có việc định kỳ (chỉ VBUS đánh thức), nên số lần vào STOP
 * phải rất nhỏ thay vì hàng nghìn lần.
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

TEST_CASE(test_24h_idle_survival_stop_count)
{
    const hal_host_stats_t *stats;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* Pin cạn → sinh tồn. */
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1400u);
    fly_run_slice(core, 30000u);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);

    hal_host_clear_stats(&host);
    fly_run_slice(core, 86400000u); /* 24 giờ */

    stats = hal_host_stats(&host);
    TEST_ASSERT(stats != NULL);
    TEST_ASSERT(stats->stop_entries <= 10u);
    TEST_ASSERT(stats->stop_ms >= 86400000u - 1000u);
    TEST_ASSERT(stats->stop_ms <= 86400000u + 1000u);
    teardown();
}

TEST_CASE(test_no_1ms_tick_in_eco)
{
    const hal_host_stats_t *stats;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    fly_run_slice(core, 3600000u); /* 1 giờ, pin khoẻ, không sự kiện */

    stats = hal_host_stats(&host);
    TEST_ASSERT(stats != NULL);
    /* ~360 lần cho chu kỳ 10 s, không phải 3,6 triệu lần của tick 1 ms. */
    TEST_ASSERT(stats->stop_entries >= 300u);
    TEST_ASSERT(stats->stop_entries <= 400u);
    TEST_ASSERT(stats->steps <= 420u);
    TEST_ASSERT(stats->stop_ms >= 3600000u - 1000u);
    teardown();
}

TEST_CASE(test_watchdog_kicks_during_steps)
{
    const hal_host_stats_t *stats;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    fly_run_slice(core, 12000u);
    stats = hal_host_stats(&host);
    TEST_ASSERT(stats != NULL);
    TEST_ASSERT(stats->wdg_kicks >= 2u);
    TEST_ASSERT(stats->wdg_kicks <= 3u);
    teardown();
}

TEST_CASE(test_survival_has_no_periodic_deadline)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1400u);
    fly_run_slice(core, 30000u);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    /* Không hẹn giờ nào: được ngủ vô hạn cho tới khi có VBUS. */
    TEST_ASSERT(fly_next_timeout_ms(core) == UINT32_MAX);
    teardown();
}
