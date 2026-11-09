/*
 * test_nvm.c — lưu/khôi phục cấu hình, boot_count, CRC hỏng, NVM trắng.
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

/* Mô phỏng MCU khởi động lại: NVM và HAL giữ nguyên, lõi mới. */
static void reboot(void)
{
    fly_destroy(core);
    core = fly_init(&host.hal);
    TEST_ASSERT(core != NULL);
}

TEST_CASE(test_persist_settings)
{
    uint8_t period[2] = {0x01u, 0x2Cu}; /* 300 */

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_MODE, (uint8_t)FLY_MODE_WATCH));
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_WAKE_CHAN, (uint8_t)FLY_WAKE_CHAN_MODEM_TCP_POLL));
    TEST_ASSERT_EQ(FLY_OK, fly_i2c_write(core, FLY_REG_WAKE_PERIOD_S, period, 2u));
    t_wr32_be(core, FLY_REG_WAKE_IN_S, 60u);

    reboot();
    TEST_ASSERT_EQ(FLY_MODE_WATCH, t_rd(core, FLY_REG_MODE));
    TEST_ASSERT_EQ(FLY_WAKE_CHAN_MODEM_TCP_POLL, t_rd(core, FLY_REG_WAKE_CHAN));
    TEST_ASSERT_EQ(300, t_rd16_be(core, FLY_REG_WAKE_PERIOD_S));
    TEST_ASSERT_EQ(60u, t_rd32_be(core, FLY_REG_WAKE_IN_S));
    teardown();
}

TEST_CASE(test_boot_count_increments)
{
    int i;

    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(1, t_rd(core, FLY_REG_BOOT_COUNT));
    for (i = 0; i < 3; i++) {
        reboot();
    }
    TEST_ASSERT_EQ(4, t_rd(core, FLY_REG_BOOT_COUNT));
    teardown();
}

TEST_CASE(test_crc_corruption_loads_defaults)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    TEST_ASSERT_EQ(FLY_OK, t_wr(core, FLY_REG_MODE, (uint8_t)FLY_MODE_WATCH));
    TEST_ASSERT_EQ(FLY_MODE_WATCH, t_rd(core, FLY_REG_MODE));

    /* Lật một byte trong phần dữ liệu của ảnh NVM → CRC sai. */
    host.nvm[4] ^= 0xFFu;

    reboot();
    TEST_ASSERT_EQ(FLY_MODE_ECO, t_rd(core, FLY_REG_MODE));
    TEST_ASSERT_EQ(FLY_FAULT_NVM, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(1, t_rd(core, FLY_REG_BOOT_COUNT));
    teardown();
}

TEST_CASE(test_blank_nvm_is_not_a_fault)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    /* Máy mới xuất xưởng: NVM trắng (0xFF). */
    fly_destroy(core);
    hal_host_reset(&host);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_BATT, 25);
    (void)hal_host_set_temp_c(&host, FLY_TEMP_AMB, 25);
    core = fly_init(&host.hal);
    TEST_ASSERT(core != NULL);

    TEST_ASSERT_EQ(FLY_FAULT_NONE, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(1, t_rd(core, FLY_REG_BOOT_COUNT));
    TEST_ASSERT_EQ(FLY_MODE_ECO, t_rd(core, FLY_REG_MODE));
    teardown();
}

TEST_CASE(test_nvm_version_mismatch_loads_defaults)
{
    if (!setup()) {
        TEST_ASSERT(0);
        return;
    }
    host.nvm[0] = 0x7Fu; /* version lạ */
    reboot();
    TEST_ASSERT_EQ(FLY_FAULT_NVM, t_rd(core, FLY_REG_FAULT_CODE));
    TEST_ASSERT_EQ(1, t_rd(core, FLY_REG_BOOT_COUNT));
    teardown();
}
