# Hợp đồng MQTT (sinh tự động)

- Nguồn: `spec/mqtt.toml`, phiên bản lược đồ 1

## 1. Chủ đề

| Tên | Mẫu |
|---|---|
| evt | `dev/{dev}/evt` |
| status | `dev/{dev}/status` |
| cmd | `dev/{dev}/cmd` |
| ack | `dev/{dev}/ack` |

## 2. Phong bì

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| v | int | có | Phiên bản lược đồ, hiện tại là 1 |
| id | string | có | ID duy nhất của bản tin, 16 hex, do nguồn gửi sinh |
| dev | string | có | Device ID, 12 ký tự [a-z0-9] |
| ts | int | có | Unix time giây UTC lúc sinh bản tin |
| type | string | có | Loại bản tin |

## 3. Sự kiện

### `motion`

- QoS 1, retained: không
- Có chuyển động, kèm clip đã ghi.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| clip_id | string | có | ID clip 16 hex |
| duration_s | int | có | Độ dài clip |
| ir | bool | có | Có bật đèn IR khi ghi |
| batt_mv | int | có | Điện áp pin lúc bắt đầu ghi |
| batt_pct | int hoặc null | có | Phần trăm pin ước tính, null nếu chưa có gauge |

### `battery`

- QoS 1, retained: không
- Đo pin định kỳ hoặc khi đổi trạng thái sạc.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| batt_mv | int | có |  |
| batt_pct | int hoặc null | có |  |
| charging | bool | có |  |
| vbus | bool | có |  |
| low | bool | có | Đang dưới ngưỡng cảnh báo |

### `temp`

- QoS 1, retained: không
- Nhiệt độ định kỳ.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| soc_c | float hoặc null | có | Nhiệt độ SoC, null nếu không đọc được |
| amb_c | float hoặc null | có |  |
| batt_c | float hoặc null | có |  |

### `fault`

- QoS 1, retained: không
- Lỗi. Gửi ngay, ưu tiên cao nhất.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| code | string | có | Tên mã lỗi, xem FAULT_CODE trong regmap |
| detail | string | không |  |

### `status`

- QoS 1, retained: có
- Trạng thái thiết bị, retained để app mở là thấy ngay.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| mode | string | có |  |
| state | string | có |  |
| fw | string | có | Phiên bản firmware ứng dụng |
| mcu_fw | string | có |  |
| proto | string | có | Phiên bản giao thức MCU, dạng 1.1 |
| rssi_dbm | int hoặc null | có |  |
| band | string hoặc null | có |  |
| uptime_s | int | có |  |
| batt_mv | int | có |  |
| sd_free_mb | int | có |  |
| wake_chan | string | có |  |
| live_url | string hoặc null | không | URL relay đang phát, null nếu không live |

### `boot`

- QoS 1, retained: không
- Thiết bị vừa khởi động, gửi một lần sau khi có mạng.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| reason | string | có | Nguồn gốc reset, lấy từ SYS_FLAGS |
| sw | string | có |  |
| boot_count | int | có |  |

### `shutdown`

- QoS 1, retained: không
- Thiết bị sắp mất nguồn, gửi ngay nếu còn mạng.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| reason | string | có |  |
| batt_mv | int | có |  |

### `clip_ready`

- QoS 1, retained: không
- Clip đã tải lên kho đối tượng, kèm URL.

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| clip_id | string | có |  |
| url | string | có |  |
| size_b | int | có |  |

## 4. Lệnh

### `live.start`

Bật xem trực tiếp trong duration_s giây.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| duration_s | int | không | 120 |  |

### `live.stop`

Tắt xem trực tiếp.

Không có tham số.

### `mode.set`

Đổi chế độ ngủ. Từ chối khi đang ghi.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| mode | string | có |  |  |

### `schedule.set`

Đặt lịch thức. Thay toàn bộ lịch cũ.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| entries | array | có |  | Tối đa 8 mục, mỗi mục {start, end, days, enabled} |

### `time.sync`

Đặt giờ thiết bị. Kết quả trả lại độ lệch đã áp dụng.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| ts | int | có |  |  |

### `status.get`

Yêu cầu gửi bản tin status ngay.

Không có tham số.

### `config.set`

Đổi một khóa cấu hình có trong danh sách cho phép.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| key | string | có |  |  |
| value | string | có |  |  |

### `clip.request`

Yêu cầu tải một clip còn lưu cục bộ lên kho.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| clip_id | string | có |  |  |

### `reboot`

Khởi động lại thiết bị.

Không có tham số.

### `ota.start`

Bắt đầu cập nhật firmware. Chưa hiện thực: phải trả lỗi NOT_IMPLEMENTED, không được giả vờ thành công.

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|---|
| url | string | có |  |  |
| sha256 | string | có |  |  |
| version | string | có |  |  |

## 5. Xác nhận

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| ok | bool | có |  |
| result | object | không |  |
| error | string hoặc null | có | Mã lỗi dạng BAD_ARGS, BUSY, NOT_IMPLEMENTED |

Mã lỗi trong `ack.error`: `BAD_ARGS`, `BAD_ID`, `BUSY`, `NOT_IMPLEMENTED`, `INTERNAL`.
