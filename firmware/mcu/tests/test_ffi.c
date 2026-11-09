/*
 * test_ffi.c — bề mặt FFI mà Python gọi qua ctypes.
 *
 * File này link chung sim/ffi.c vào binary test, nên cùng một lần chạy
 * `build.py test` phủ cả lõi lẫn adapter FFI.
 */
#include "test.h"

#include "../sim/ffi.h"
#include "flytex/regs_gen.h"

TEST_CASE(test_ffi_lifecycle_and_inputs)
{
    void *h = fsim_new();

    TEST_ASSERT(h != NULL);
    TEST_ASSERT_EQ(0u, (long)fsim_now_ms(h));
    TEST_ASSERT_EQ(FLY_OK, fsim_set_input(h, FLY_PIN_VBUS, 1));
    /* RI là input chân 4, dùng chung fsim_set_input, không cần hàm mới. */
    TEST_ASSERT_EQ(FLY_OK, fsim_set_input(h, FLY_PIN_MODEM_RI, 1));
    TEST_ASSERT_EQ(FLY_EINVAL, fsim_set_input(h, FLY_PIN_SOC_PWR, 1));
    TEST_ASSERT_EQ(FLY_EINVAL, fsim_set_adc_mv(h, 9, 1000u));
    TEST_ASSERT_EQ(FLY_EINVAL, fsim_set_temp_c(h, 9, 25));
    fsim_step(h);
    fsim_free(h);
    fsim_free(NULL); /* phải an toàn với NULL */
}

TEST_CASE(test_ffi_i2c_reads_proto_ver)
{
    void *h = fsim_new();
    uint8_t ver = 0u;
    uint8_t buf[2] = {0u, 0u};
    uint8_t value = 0x55u;
    uint8_t cmd = (uint8_t)FLY_CMD_SOC_WAKE;
    uint8_t status = 0u;

    TEST_ASSERT(h != NULL);
    TEST_ASSERT_EQ(FLY_OK, fsim_i2c_read(h, FLY_REG_PROTO_VER, &ver, 1));
    TEST_ASSERT_EQ(0x11, ver);

    TEST_ASSERT_EQ(FLY_OK, fsim_i2c_read(h, 0x00, buf, 2));
    TEST_ASSERT_EQ(0x11, buf[0]);
    TEST_ASSERT_EQ(0x10, buf[1]);

    /* Ghi thanh ghi chỉ đọc: NACK. */
    TEST_ASSERT_EQ(FLY_EIO, fsim_i2c_write(h, FLY_REG_PROTO_VER, &value, 1));

    TEST_ASSERT_EQ(FLY_OK, fsim_i2c_write(h, FLY_REG_CMD, &cmd, 1));
    TEST_ASSERT_EQ(FLY_OK, fsim_i2c_read(h, FLY_REG_STATUS, &status, 1));
    TEST_ASSERT(status & FLY_STATUS_SOC_READY);
    fsim_free(h);
}

TEST_CASE(test_ffi_stats_json_shape)
{
    void *h = fsim_new();
    const char *json;
    unsigned stop_entries = 0u;
    unsigned stop_ms = 0u;
    unsigned wdg_kicks = 0u;
    unsigned nacks = 0u;
    unsigned steps = 0u;
    int parsed;

    TEST_ASSERT(h != NULL);
    TEST_ASSERT_EQ(FLY_OK, fsim_set_adc_mv(h, FLY_ADC_VBAT, 1650u));
    TEST_ASSERT_EQ(FLY_OK, fsim_set_temp_c(h, FLY_TEMP_BATT, 25));
    TEST_ASSERT_EQ(FLY_OK, fsim_set_temp_c(h, FLY_TEMP_AMB, 25));
    fsim_step(h);
    TEST_ASSERT_EQ(1000, fsim_advance_ms(h, 1000u));
    TEST_ASSERT_EQ(1000u, (long)fsim_now_ms(h));

    json = fsim_stats_json(h);
    TEST_ASSERT(json != NULL);
    TEST_ASSERT(json[0] == '{');
    TEST_ASSERT(json[strlen(json) - 1u] == '}');
    TEST_ASSERT(strstr(json, "\"stop_entries\":") != NULL);
    TEST_ASSERT(strstr(json, "\"stop_ms\":") != NULL);
    TEST_ASSERT(strstr(json, "\"wdg_kicks\":") != NULL);
    TEST_ASSERT(strstr(json, "\"i2c_nacks\":") != NULL);
    TEST_ASSERT(strstr(json, "\"steps\":") != NULL);

    parsed = sscanf(json,
                    "{\"stop_entries\":%u,\"stop_ms\":%u,\"wdg_kicks\":%u,"
                    "\"i2c_nacks\":%u,\"steps\":%u}",
                    &stop_entries, &stop_ms, &wdg_kicks, &nacks, &steps);
    TEST_ASSERT_EQ(5, parsed);
    TEST_ASSERT(stop_entries >= 1u);
    TEST_ASSERT(stop_ms >= 1000u);
    TEST_ASSERT(steps >= 2u);
    TEST_ASSERT(nacks == 0u);
    fsim_free(h);
}

TEST_CASE(test_ffi_outputs_and_nack_counter)
{
    void *h = fsim_new();
    uint8_t buf[1] = {0u};
    uint8_t cmd = (uint8_t)FLY_CMD_SOC_WAKE;
    const char *json;

    TEST_ASSERT(h != NULL);
    /* Chân vào không phải chân ra. */
    TEST_ASSERT_EQ(-1, fsim_get_output(h, FLY_PIN_PIR));
    TEST_ASSERT_EQ(-1, fsim_get_output(h, FLY_PIN_MODEM_RI));
    TEST_ASSERT_EQ(0, fsim_get_output(h, FLY_PIN_SOC_PWR));
    /* Chưa có sự kiện: MCU_IRQ đang thả (mức cao). */
    TEST_ASSERT_EQ(1, fsim_get_output(h, FLY_PIN_IRQ));

    /* Đọc địa chỉ ngoài dải: NACK và được đếm. */
    TEST_ASSERT_EQ(FLY_EIO, fsim_i2c_read(h, 0xFF, buf, 1));
    json = fsim_stats_json(h);
    TEST_ASSERT(strstr(json, "\"i2c_nacks\":1") != NULL);

    TEST_ASSERT_EQ(FLY_OK, fsim_i2c_write(h, FLY_REG_CMD, &cmd, 1));
    TEST_ASSERT_EQ(1, fsim_get_output(h, FLY_PIN_SOC_PWR));
    fsim_free(h);
}
