# 16 — Vận hành

- Trạng thái: hướng dẫn đi kèm mã trong repo
- Ngày: 2026-11-09

Tài liệu này là việc phải làm khi có thiết bị trong tay; không phải mô tả cái đã chạy trên phần cứng.

## 1. Trên máy phát triển

| Việc | Lệnh | Ghi chú |
|---|---|---|
| Sinh lại mã từ spec | `python spec/generate.py` | Sau mọi thay đổi `spec/*.toml` |
| Kiểm file sinh | `python spec/generate.py --check` | CI chạy lệnh này |
| Chạy toàn bộ test | `python run_tests.py` | Cần `gcc` hoặc `clang` cho firmware |
| Chỉ test ứng dụng | `python app/tests/test_power.py` | Mỗi file chạy độc lập được |
| Mô phỏng | `python sim/run.py --scenario basic` | Không cần phần cứng |
| Báo cáo năng lượng | `python tools/measure/cli.py report --csv <file>` | Mặc định pack 15 Ah (D-18) |

Không cần `pip install`. Nếu muốn MQTT thật: `pip install paho-mqtt` (tùy chọn, chỉ dùng trên thiết bị hoặc test tích hợp).

## 2. Cấp phát một thiết bị

```text
/data/identity/device_id     # 12 ký tự [a-z0-9]
/data/identity/cert.pem      # chứng chỉ thiết bị
/data/identity/key.pem       # khóa riêng, quyền 600
/data/identity/ca.pem        # CA của dự án
/data/config.json            # cấu hình, xem app/flytex/config.py
```

1. Sinh `device_id`, ghi vào phân vùng định danh.
2. Sinh khóa và CSR; ký bằng CA của dự án (không dùng chung khóa giữa các máy).
3. Nạp chứng chỉ; kiểm tra quyền file.
4. Ghi `config.json` với APN, host MQTT, relay, chế độ ngủ.
5. Kiểm: ứng dụng kết nối được MQTT bằng chứng chỉ riêng; sai chứng chỉ phải bị từ chối.

Không có mật khẩu mặc định. Không đưa khóa vào image firmware.

## 3. Chạy trên thiết bị (khi có board)

Tệp dịch vụ thật nằm ở [deploy/systemd/flytex-device.service](../deploy/systemd/flytex-device.service); hướng dẫn cài ở [deploy/README.md](../deploy/README.md). Tóm tắt: chạy dưới người dùng `flytex` không đặc quyền, chỉ ghi `/data`, có `WatchdogSec`, giới hạn vòng restart.

Cần kiểm trên thiết bị: Python và module chuẩn có trong rootfs; quyền đọc `/dev/i2c-*`, `/dev/ttyUSB*`; quyền ghi `/data`.

## 4. Gỡ lỗi tại hiện trường

| Triệu chứng | Kiểm trước | Ghi chú |
|---|---|---|
| Không lên mạng | Log `modemd`: SIM, đăng ký, APN, cường độ sóng | Không reset modem liên tục; mỗi lần chờ đủ thời gian |
| Không nhận lệnh khi ngủ | `WAKE_CHAN`, SIM có nhận SMS, chân RI | Xem [15](15-giao-thuc-va-cloud.md) §4 |
| Không xem trực tiếp được | Relay, token WHEP hết hạn, bitrate | Hạ độ phân giải trước khi kết luận hỏng |
| Pin tụt nhanh | `VBAT_MV`, dòng ngủ, BMS tự tiêu | Đo bằng header J_MEAS, không suy từ phần trăm |
| Nóng, giảm hiệu năng | Nhiệt SoC, nhiệt vỏ | Đo M-22, M-40 |
| Firmware hỏng, không OTA được | Đường nạp dịch vụ (pad/mux) | Xem [03](03-giao-dien.md) §4.1 |

## 5. Quy trình đo G0

1. Chọn một phép đo trong [08](08-kiem-chung.md), ví dụ M-01.
2. Ghi điều kiện: board, nguồn, nhiệt độ phòng, dụng cụ, người đo.
3. Nhập vào CSV bằng `tools/measure` (không ghi 0 cho "chưa đo"; để trống + NA).
4. Sinh báo cáo, đính kèm ảnh chụp màn hình dụng cụ.
5. Chỉ khi đủ bộ đo mới cập nhật bảng năng lượng ở [02](02-thiet-ke-nguon.md) §3 — và cập nhật ở một nơi, các nơi khác trỏ tới.

## 6. Trước khi đặt board

- [ ] G0 đã qua, có bảng đo thật ([07](07-ke-hoach-phat-trien.md)).
- [ ] Không vi phạm điều kiện dừng ([13](13-tinh-kha-thi.md) §9.3).
- [ ] `python run_tests.py` xanh.
- [ ] `python spec/generate.py --check` xanh.
- [ ] `python -m hardware.calc.cli --check` xanh và các giá trị trong [pwr-design](../hardware/pwr-design.md) đã được đọc, chấp nhận.
- [ ] BOM có MPN thật cho mọi dòng, không còn "chưa chọn".
- [ ] Board thử footprint đã đặt và nhận ([hardware/footprint-test/checklist.md](../hardware/footprint-test/checklist.md)).
- [ ] Chỉ đổi một board so với lần trước.
