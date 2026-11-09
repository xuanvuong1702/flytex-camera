/*
 * ffi.h — bề mặt FFI cho mô phỏng phía Python (ctypes).
 *
 * Mọi hàm nhận handle do fsim_new() trả về. Tên hàm phải giữ đúng chính xác,
 * không static, để ctypes tìm thấy trong flytexmcu.dll / libflytexmcu.so.
 *
 * Quy ước lỗi: 0 là thành công, số âm là lỗi (cùng mã với hal.h).
 */
#ifndef FLYTEX_SIM_FFI_H
#define FLYTEX_SIM_FFI_H

#if defined(_WIN32) && defined(FSIM_BUILD_DLL)
#define FSIM_API __declspec(dllexport)
#else
#define FSIM_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Tạo/giải phóng một phiên mô phỏng. fsim_new trả NULL nếu hết bộ nhớ. */
FSIM_API void *fsim_new(void);
FSIM_API void fsim_free(void *h);

/* Đặt mức chân vào (chỉ chân input). Trả 0 hoặc FLY_EINVAL. */
FSIM_API int fsim_set_input(void *h, int pin, int level);

/* Đặt mV tại chân ADC. */
FSIM_API int fsim_set_adc_mv(void *h, int ch, unsigned mv);

/* Đặt nhiệt độ; c = -128 nghĩa là không có cảm biến (temp_c trả FLY_ENOSYS). */
FSIM_API int fsim_set_temp_c(void *h, int sensor, int c);

/* Chạy đúng một bước lõi. */
FSIM_API void fsim_step(void *h);

/* Chạy vòng tickless trong ms mili giây mô phỏng; trả số ms đã trôi. */
FSIM_API int fsim_advance_ms(void *h, unsigned ms);

/* Truy cập regmap như master I2C. Trả 0 hoặc số âm (âm = NACK/lỗi). */
FSIM_API int fsim_i2c_read(void *h, int reg, unsigned char *buf, int len);
FSIM_API int fsim_i2c_write(void *h, int reg, const unsigned char *buf, int len);

/* Mức chân ra; -1 nếu không phải chân ra. */
FSIM_API int fsim_get_output(void *h, int pin);

/*
 * Chuỗi JSON thống kê, ví dụ
 * {"stop_entries":5,"stop_ms":3600000,"wdg_kicks":10,"i2c_nacks":0,"steps":42}
 * Con trỏ hợp lệ tới lần gọi tiếp theo trên cùng handle.
 */
FSIM_API const char *fsim_stats_json(void *h);

/* Thời gian mô phỏng hiện tại, ms. */
FSIM_API unsigned fsim_now_ms(void *h);

#ifdef __cplusplus
}
#endif

#endif /* FLYTEX_SIM_FFI_H */
