/*
 * test_sched.c — lịch WAKE_IN_S và kênh đánh thức WAKE_CHAN.
 *
 * Gồm kênh SMS qua chân MODEM_RI: cạnh lên chỉ có nghĩa khi WAKE_CHAN = SMS.
 */
#include "test.h"

#include "../hal/host/hal_host.h"
#include "flytex/core.h"
#include "flytex/regs_gen.h"

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

TEST_CASE(test_wake_in_counts_down)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    t_wr32_be(core, FLY_REG_WAKE_IN_S, 5u);
    TEST_ASSERT_EQ(5u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    advance(2000u);
    TEST_ASSERT_EQ(3u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    advance(2000u);
    TEST_ASSERT_EQ(1u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    teardown();
}

TEST_CASE(test_wake_in_expiry_posts_schedule)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    t_wr32_be(core, FLY_REG_WAKE_IN_S, 5u);
    advance(5001u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_SCHEDULE);
    TEST_ASSERT_EQ(0u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_wake_in_persists_in_nvm)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    t_wr32_be(core, FLY_REG_WAKE_IN_S, 60u);
    /* Khởi động lại MCU: NVM còn nguyên, lõi mới phải đọc lại lịch. */
    fly_destroy(core);
    core = fly_init(&host.hal);
    TEST_ASSERT(core != NULL);
    TEST_ASSERT_EQ(60u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    teardown();
}

TEST_CASE(test_wake_alarm_modem_tcp_poll)
{
    uint8_t period[2] = {0x00u, 0x02u}; /* 2 s để test nhanh */

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_WAKE_CHAN, (uint8_t)FLY_WAKE_CHAN_MODEM_TCP_POLL));
    TEST_ASSERT_EQ(FLY_OK, fly_i2c_write(core, FLY_REG_WAKE_PERIOD_S, period, 2u));
    TEST_ASSERT_EQ(2u, t_rd16_be(core, FLY_REG_WAKE_PERIOD_S));

    advance(2100u);
    /* Đã bật rail modem và đang chờ chân STATUS. */
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);

    (void)hal_host_set_input(&host, FLY_PIN_MODEM_STATUS, 1);
    advance(10u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_wake_alarm_modem_no_boot)
{
    uint8_t period[2] = {0x00u, 0x02u};

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_WAKE_CHAN, (uint8_t)FLY_WAKE_CHAN_MODEM_TCP_POLL));
    TEST_ASSERT_EQ(FLY_OK, fly_i2c_write(core, FLY_REG_WAKE_PERIOD_S, period, 2u));

    /* Modem không lên trong 30 s: vẫn báo WAKE_ALARM nhưng ghi lỗi. */
    advance(34000u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);
    TEST_ASSERT_EQ(FLY_FAULT_MODEM_NO_BOOT, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_ri_wakes_on_sms_channel)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_WAKE_CHAN, (uint8_t)FLY_WAKE_CHAN_SMS));
    /* WAKE_ALARM là bit 6, mặc định bị EVENT_MASK 0x3F che. */
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_EVENT_MASK, 0x7Fu));

    (void)hal_host_set_input(&host, FLY_PIN_MODEM_RI, 1);
    fly_step(core);

    /* Kiểm IRQ trước khi đọc EVENT, vì đọc EVENT sẽ xóa sự kiện và thả IRQ. */
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_IRQ));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);
    teardown();
}

TEST_CASE(test_ri_ignored_when_channel_off)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_WAKE_CHAN_OFF, t_rd(core, FLY_REG_WAKE_CHAN));

    (void)hal_host_set_input(&host, FLY_PIN_MODEM_RI, 1);
    fly_step(core);

    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_EVENT) & FLY_EVENT_WAKE_ALARM);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}
