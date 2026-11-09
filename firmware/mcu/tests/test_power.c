/*
 * test_power.c — máy trạng thái nguồn: bật SoC, quá hạn bắt tay, tắt an toàn,
 * sinh tồn.
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

/* PIR: một xung đủ dài để vượt debounce. Trả về sau khi lõi đã bật rail. */
static void pir_pulse(void)
{
    (void)hal_host_set_input(&host, FLY_PIN_PIR, 1);
    advance(150u);
    (void)hal_host_set_input(&host, FLY_PIN_PIR, 0);
}

TEST_CASE(test_pir_powers_soc)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    pir_pulse();
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_PIR);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SOC_POWER_ON);
    /* Chưa có SOC_READY nên chưa được coi là đã bật xong. */
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SOC_READY);
    teardown();
}

TEST_CASE(test_schedule_powers_soc)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    t_wr32_be(core, FLY_REG_WAKE_IN_S, 5u);
    advance(5001u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_SCHEDULE);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(0u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    teardown();
}

TEST_CASE(test_soc_boot_timeout_sets_fault)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    pir_pulse();
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    advance(20000u);
    TEST_ASSERT_EQ(FLY_FAULT_SOC_NO_BOOT, t_rd(core, FLY_REG_FAULT_CODE));
    /* Đã cắt rail và đang chờ thử lại. */
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_soc_boot_retries_then_survival)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    pir_pulse();
    advance(70000u);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT_EQ(FLY_FAULT_SOC_NO_BOOT, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    teardown();
}

TEST_CASE(test_shutdown_handshake_success)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_SOC_WAKE));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));

    /* Pin dưới ngưỡng cảnh báo: yêu cầu SoC tắt an toàn. */
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1525u); /* → 3050 mV */
    advance(1000u);
    {
        uint8_t events = t_rd(core, FLY_REG_EVENT);
        TEST_ASSERT(events & FLY_EVENT_LOW_BATT);
        TEST_ASSERT(events & FLY_EVENT_SHUTDOWN_REQ);
    }
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_LOW_BATT);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));

    /* SoC đóng file xong. */
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_SOC_SHUTDOWN_DONE));
    advance(499u);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    advance(2u);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_shutdown_timeout_forced_cut)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_SOC_WAKE));
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1525u);
    advance(1000u);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_SHUTDOWN_REQ);

    /* Không gửi SOC_SHUTDOWN_DONE: quá 10 s thì cắt cưỡng bức. */
    advance(11000u);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(FLY_FAULT_SOC_NO_HANDSHAKE, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_survival_enter_and_exit_on_vbus)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1400u); /* → 2800 mV */
    advance(1u);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(FLY_FAULT_BATT_UNDERVOLTAGE, t_rd(core, FLY_REG_FAULT_CODE));

    /* Cắm USB-C và pin hồi phục → thoát sinh tồn. */
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1650u);
    (void)hal_host_set_input(&host, FLY_PIN_VBUS, 1);
    advance(1u);
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_STATUS) & FLY_STATUS_SURVIVAL);
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_VBUS_PRESENT);
    TEST_ASSERT(t_rd(core, FLY_REG_EVENT) & FLY_EVENT_VBUS_CHANGE);
    teardown();
}

TEST_CASE(test_modem_rail_commands)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_MODEM_ON));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_MODEM_POWER_ON);

    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_MODEM_OFF));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    teardown();
}

TEST_CASE(test_modem_reset_pulse)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_MODEM_RESET));
    TEST_ASSERT_EQ(FLY_MODEM_RESET_ACTIVE_LEVEL, hal_host_get_output(&host, FLY_PIN_MODEM_RESET));
    advance(FLY_MODEM_RESET_PULSE_MS + 1u);
    TEST_ASSERT_EQ(FLY_MODEM_RESET_ACTIVE_LEVEL ? 0 : 1, hal_host_get_output(&host, FLY_PIN_MODEM_RESET));
    teardown();
}
