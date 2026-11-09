/*
 * test_regmap.c — hợp đồng thanh ghi: quyền truy cập, NACK, latch, commit,
 * EVENT xóa khi đọc, MCU_IRQ theo EVENT_MASK, CMD.
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

TEST_CASE(test_proto_and_fw_version)
{
    uint8_t buf[2] = {0u, 0u};

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(0x11, t_rd(core, FLY_REG_PROTO_VER));
    TEST_ASSERT_EQ(0x10, t_rd(core, FLY_REG_FW_VER));
    TEST_ASSERT_EQ(FLY_OK, t_rd_block(core, FLY_REG_PROTO_VER, buf, 2u));
    TEST_ASSERT_EQ(0x11, buf[0]);
    TEST_ASSERT_EQ(0x10, buf[1]);
    teardown();
}

TEST_CASE(test_write_readonly_nacked)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_PROTO_VER, 0x22u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_FW_VER, 0x00u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_STATUS, 0x00u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_FAULT_CODE, 0x00u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_SYS_FLAGS, 0x00u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_BOOT_COUNT, 0x00u));
    /* Ghi vào EVENT cũng là ghi thanh ghi chỉ đọc. */
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, FLY_REG_EVENT, 0x00u));
    TEST_ASSERT_EQ(0x11, t_rd(core, FLY_REG_PROTO_VER));
    teardown();
}

TEST_CASE(test_read_writeonly_nacked)
{
    uint8_t value = 0u;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_EIO, fly_i2c_read(core, FLY_REG_CMD, &value, 1u));
    teardown();
}

TEST_CASE(test_out_of_range_nacked)
{
    uint8_t buf[2] = {0u, 0u};

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, 0x18u, 0x01u));
    TEST_ASSERT_EQ(FLY_EIO, t_wr(core, 0x7Fu, 0x01u));
    TEST_ASSERT_EQ(FLY_EIO, fly_i2c_read(core, 0x18u, buf, 1u));
    TEST_ASSERT_EQ(FLY_EIO, fly_i2c_read(core, 0xFFu, buf, 1u));
    /* Nhóm vắt qua cuối dải cũng phải NACK toàn bộ. */
    TEST_ASSERT_EQ(FLY_EIO, t_rd_block(core, FLY_REG_BOOT_COUNT, buf, 2u));
    teardown();
}

TEST_CASE(test_event_clear_on_read)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_input(&host, FLY_PIN_VBUS, 1);
    fly_step(core);
    TEST_ASSERT_EQ(FLY_EVENT_VBUS_CHANGE, t_rd(core, FLY_REG_EVENT));
    TEST_ASSERT_EQ(0u, t_rd(core, FLY_REG_EVENT));
    teardown();
}

TEST_CASE(test_irq_follows_event_mask)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_input(&host, FLY_PIN_VBUS, 1);
    fly_step(core);
    /* Có sự kiện và mask cho phép → kéo MCU_IRQ xuống mức thấp. */
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_IRQ));

    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_EVENT_MASK, 0x00u));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_IRQ));
    TEST_ASSERT_EQ(FLY_EVENT_VBUS_CHANGE, t_rd(core, FLY_REG_EVENT));

    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_EVENT_MASK, 0x3Fu));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_IRQ));
    teardown();
}

TEST_CASE(test_vbat_latch_holds_value)
{
    uint8_t hi;
    uint8_t lo;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1600u); /* → 3200 mV */
    fly_step(core);
    hi = t_rd(core, FLY_REG_VBAT_MV);
    lo = t_rd(core, FLY_REG_VBAT_MV + 1u);
    TEST_ASSERT_EQ(0x0Cu, hi);
    TEST_ASSERT_EQ(0x80u, lo);

    /* Giá trị đo đổi, nhưng byte thấp phải trả giá trị đã chốt. */
    (void)hal_host_set_adc_mv(&host, FLY_ADC_VBAT, 1700u); /* → 3400 mV */
    fly_run_slice(core, 10000u);
    TEST_ASSERT_EQ(0x80u, t_rd(core, FLY_REG_VBAT_MV + 1u));
    TEST_ASSERT_EQ(0x0Du, t_rd(core, FLY_REG_VBAT_MV));
    TEST_ASSERT_EQ(0x48u, t_rd(core, FLY_REG_VBAT_MV + 1u));
    teardown();
}

TEST_CASE(test_wake_in_commits_on_last_byte)
{
    uint8_t part[3] = {0x00u, 0x00u, 0x00u};
    uint8_t last = 0x2Au; /* 42 giây, byte thấp ở địa chỉ 0x0F */

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, fly_i2c_write(core, FLY_REG_WAKE_IN_S, part, 3u));
    /* Chưa ghi byte cuối 0x0F: giá trị cũ vẫn là 0. */
    TEST_ASSERT_EQ(0u, t_rd32_be(core, FLY_REG_WAKE_IN_S));

    TEST_ASSERT_EQ(FLY_OK, fly_i2c_write(core, (uint8_t)(FLY_REG_WAKE_IN_S + 3u), &last, 1u));
    TEST_ASSERT_EQ(42u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    teardown();
}

TEST_CASE(test_unknown_cmd_sets_bad_cmd)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, 0x7Fu));
    TEST_ASSERT_EQ(FLY_FAULT_BAD_CMD, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT(t_rd(core, FLY_REG_STATUS) & FLY_STATUS_FAULT);
    /* Không được làm gì: cả hai rail vẫn tắt. */
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    teardown();
}

TEST_CASE(test_soc_wake_cmd_sets_ready)
{
    uint8_t status;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    status = t_rd(core, FLY_REG_STATUS);
    TEST_ASSERT_EQ(0, status & FLY_STATUS_SOC_READY);
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_SOC_WAKE));
    status = t_rd(core, FLY_REG_STATUS);
    TEST_ASSERT(status & FLY_STATUS_SOC_READY);
    TEST_ASSERT(status & FLY_STATUS_SOC_POWER_ON);
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_SOC_PWR));
    teardown();
}

TEST_CASE(test_mode_watch_enables_modem_rail)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_MODE, (uint8_t)FLY_MODE_WATCH));
    TEST_ASSERT_EQ(FLY_MODE_WATCH, t_rd(core, FLY_REG_MODE));
    TEST_ASSERT_EQ(1, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));

    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_MODE, (uint8_t)FLY_MODE_ECO));
    TEST_ASSERT_EQ(FLY_MODE_ECO, t_rd(core, FLY_REG_MODE));
    TEST_ASSERT_EQ(0, hal_host_get_output(&host, FLY_PIN_MODEM_PWR));
    teardown();
}

TEST_CASE(test_invalid_mode_and_channel_rejected)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_EINVAL, t_wr(core, FLY_REG_MODE, 5u));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_MODE));
    TEST_ASSERT_EQ(FLY_EINVAL, t_wr(core, FLY_REG_WAKE_CHAN, 9u));
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_WAKE_CHAN));
    teardown();
}

TEST_CASE(test_status_vbus_and_modem_ready)
{
    uint8_t status;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    (void)hal_host_set_input(&host, FLY_PIN_VBUS, 1);
    (void)hal_host_set_input(&host, FLY_PIN_MODEM_STATUS, 1);
    fly_step(core);
    status = t_rd(core, FLY_REG_STATUS);
    TEST_ASSERT(status & FLY_STATUS_VBUS_PRESENT);
    TEST_ASSERT(status & FLY_STATUS_MODEM_READY);
    TEST_ASSERT_EQ(0, status & FLY_STATUS_SURVIVAL);
    teardown();
}

TEST_CASE(test_clear_fault_cmd)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, 99u));
    TEST_ASSERT_EQ(FLY_FAULT_BAD_CMD, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_CMD, (uint8_t)FLY_CMD_CLEAR_FAULT));
    TEST_ASSERT_EQ(FLY_FAULT_NONE, t_rd(core, FLY_REG_FAULT_CODE));
    teardown();
}

TEST_CASE(test_uptime_and_boot_count)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(1, t_rd(core, FLY_REG_BOOT_COUNT));
    fly_run_slice(core, 5000u);
    /* UPTIME_S là 2 byte big-endian: 5 s = 0x0005. */
    TEST_ASSERT_EQ(0, t_rd(core, FLY_REG_UPTIME_S));
    TEST_ASSERT_EQ(5, t_rd(core, FLY_REG_UPTIME_S + 1u));
    teardown();
}
