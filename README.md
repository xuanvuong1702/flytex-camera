# Flytex Camera

Camera 4G chạy pin cho ngoài trời: phát hiện chuyển động, ghi hình cục bộ, xem trực tiếp qua 4G, ngủ sâu và nhận lệnh từ xa.

Đây là phiên bản **tiền thương mại**: đủ đơn giản để dựng prototype nhanh, nhưng các giao diện (connector, rail nguồn, giao thức MCU↔SoC, cơ khí) được chốt sao cho lên production không phải làm lại.

Repo này **làm lại từ đầu**. Nó kế thừa *bài học* từ dự án CAM4G ([xuanvuong1702/camera-4G](https://github.com/xuanvuong1702/camera-4G)), không kế thừa file thiết kế nào của dự án đó.

## Trạng thái

| Hạng mục | Trạng thái |
|---|---|
| Tài liệu thiết kế | v1.1, đã qua rà soát khả thi |
| Đặc tả giao diện máy đọc được | Có: regmap, J_B2B, MQTT sinh tự động từ `spec/` |
| Firmware MCU | Có lõi + HAL giả + **64 test** host; port STM32L0 còn là khung |
| Ứng dụng Linux | Có module + **182 test** host; chưa chạy camera thật |
| Mô phỏng end-to-end | Có: firmware C thật + ứng dụng thật, **5 kịch bản** |
| Gói thiết kế phần cứng | Tính toán PWR, hình học board + SVG, BOM Rev A/B, sổ linh kiện, bring-up; **67 test** |
| Sổ linh kiện | **15 linh kiện + 4 module**; 0 blocker cứng, 1 giả định PACK ([docs/18](docs/18-tai-lieu-linh-kien.md)) |
| Công cụ đo và kiểm tài liệu | Có, **124 test**; nhập PPK2, lint include C, kiểm tài liệu, checklist readiness |
| Kiểm thử toàn repo | **490 test + 5 kịch bản**, 41/41 bước đạt: `python run_tests.py` |
| Sẵn sàng dựng prototype | **CHƯA ĐẠT** — vòng 7 phát hiện lỗi sạc/CI/BOM/pin ([docs/17](docs/17-san-sang-prototype.md)) |
| Phần cứng | **Chưa có**: chưa có Gerber/PCB; gói thiết kế đã đủ để vẽ schematic |
| Số đo thực | **Chưa có.** Mọi con số công suất, nhiệt, thời gian chạy đều là ước tính |

Phân tích khả thi, các lỗi thiết kế phải sửa và lộ trình: [docs/13-tinh-kha-thi.md](docs/13-tinh-kha-thi.md).

## Quyết định đã chốt

| # | Quyết định |
|---|---|
| 1 | Làm lại từ đầu, tài liệu nằm trong repo này |
| 2 | Pin: **pack 1S LFP có sẵn BMS** (không tự ghép cell rời) |
| 3 | Sạc bằng **USB-C 5 V** |

Các quyết định còn lại đều ở trạng thái *đề xuất* hoặc *mở*, xem [nhật ký quyết định](docs/11-nhat-ky-quyet-dinh.md).

## Hướng thiết kế trong một đoạn

Tách sản phẩm thành ba phần theo mức rủi ro: **board nguồn (PWR)**, **board compute (CMP)** và **breakout modem (MDM)**, nối bằng giao diện đã chốt. Dùng module OEM cho phần khó (SoC Core1106D/RV1106, modem EC200U-EU, camera có IR tích hợp). Đo trên dev board trước khi vẽ board nào. Mỗi lần đặt board chỉ đổi một board, và mọi footprint tự tạo phải qua board thử footprint trước.

## Nguyên tắc làm việc

1. **Đo trước, chốt sau.** Số liệu là ước tính cho đến khi có phép đo.
2. **Giảm số thứ phải tự thiết kế.** Phần khó dùng module OEM.
3. **Chốt giao diện, không chốt hiện thực.** Đổi bên trong một board không được làm đổi board khác.
4. **Mỗi con số chỉ có một nguồn sự thật.** Các tài liệu khác chỉ trỏ tới, không chép lại. Nay được CI thực thi: `spec/generate.py --check`.
5. **Không đoán chân IC hay footprint.** Đối chiếu datasheet và kiểm bằng linh kiện thật.
6. **Không tuyên bố "chạy được" khi chưa có phép đo.** Chức năng chưa làm phải trả lỗi rõ, không trả giá trị giả.

## Nhãn dùng trong tài liệu

| Nhãn | Ý nghĩa |
|---|---|
| `[ĐÃ CHỐT]` | Chủ dự án đã quyết định |
| `[ĐỀ XUẤT]` | Khuyến nghị thiết kế, chờ xác nhận |
| `[ƯỚC TÍNH]` | Con số chưa đo |
| `[CHƯA XÁC MINH]` | Cần kiểm datasheet hoặc thử thực tế |
| `[ĐÃ XÁC MINH]` | Đã đối chiếu tài liệu nguồn, ghi ở [13](docs/13-tinh-kha-thi.md) §3 |
| `[KẾ THỪA]` | Lấy từ CAM4G, cần xác nhận lại cho dự án này |

## Cấu trúc repo

| Đường dẫn | Nội dung |
|---|---|
| `docs/` | Tài liệu thiết kế, phân tích khả thi, kiến trúc phần mềm bản chốt |
| `spec/` | Nguồn sự thật máy đọc được: regmap, pinout, MQTT; bộ sinh mã |
| `firmware/mcu/` | Firmware MCU: lõi C, HAL host, HAL STM32L0 (khung), test, FFI |
| `app/` | Ứng dụng Linux trên SoC (Python), test, dịch vụ |
| `sim/` | Mô phỏng end-to-end: firmware C qua FFI + ứng dụng + modem/cloud giả |
| `tools/measure/` | Nhập số đo G0, sinh báo cáo năng lượng |
| `tools/docs_check/` | Kiểm tra tham chiếu, mục lục, bảng, file sinh |
| `hardware/` | BOM giai đoạn 0, checklist board thử footprint |
| `deploy/` | Tệp systemd và hướng dẫn cài lên thiết bị |
| `.github/workflows/` | CI chạy toàn bộ test trên Ubuntu |

## Bắt đầu nhanh

```powershell
# Kiểm tra file sinh có khớp spec không (không ghi gì)
python spec/generate.py --check

# Sinh lại mã và bảng sau khi sửa spec/*.toml
python spec/generate.py

# Chạy toàn bộ: spec, hardware, firmware C, ứng dụng, công cụ, mô phỏng
python run_tests.py

# Checklist "sẵn sàng dựng prototype" (docs/17)
python tools/readiness.py --full

# Cổng trước khi đặt hàng: còn blocker thì không đặt (docs/18)
python -m hardware.parts.check --strict

# Chỉ chạy mô phỏng end-to-end
python sim/run.py --scenario basic

# Báo cáo năng lượng từ file đo (mẫu rỗng, chưa có số thật)
python tools/measure/cli.py report --csv tools/measure/samples/g0-template.csv
```

Không cần phần cứng, không cần cài thêm gói Python. Firmware C cần `gcc` hoặc `clang`.

## Kiểm thử

| Tầng | Lệnh | Số lượng |
|---|---|---|
| Đặc tả và bộ sinh | `python -m unittest discover -s spec/tests` | 29 |
| Thiết kế PWR/CMP (tính toán, hình học, BOM, sổ linh kiện) | `hardware/calc/`, `hardware/geom/`, `hardware/bom/`, `hardware/parts/` | 57 |
| Firmware MCU (C, host) | `python firmware/mcu/tests/build.py test` | 64 |
| Ứng dụng Linux (Python) | `python -m unittest discover -s app/tests -t .` | 188 |
| Công cụ đo và kiểm tài liệu | `python -m unittest discover -s tools -t .` | 120 (+4 trong `tools/tests`) = 124 |
| Mô phỏng end-to-end | `python sim/run.py --scenario all` | 5 kịch bản |
| Tất cả | `python run_tests.py` | 41 bước |

Test không cần phần cứng. Test cần phần cứng nằm ở [docs/08](docs/08-kiem-chung.md) và vẫn là "Chưa làm".

## Mục lục

| File | Nội dung |
|---|---|
| [00-yeu-cau.md](docs/00-yeu-cau.md) | Yêu cầu, ngoài phạm vi, giả định |
| [01-kien-truc.md](docs/01-kien-truc.md) | Kiến trúc hệ thống, ba phần, trạng thái nguồn |
| [02-thiet-ke-nguon.md](docs/02-thiet-ke-nguon.md) | Pin, sạc USB-C, boost/buck, ngân sách năng lượng |
| [03-giao-dien.md](docs/03-giao-dien.md) | Rail, connector, tín hiệu giữa các board |
| [04-firmware.md](docs/04-firmware.md) | Firmware MCU và ứng dụng Linux |
| [05-ket-noi-va-cloud.md](docs/05-ket-noi-va-cloud.md) | Modem, mạng, cloud, xem trực tiếp |
| [06-co-khi-nhiet.md](docs/06-co-khi-nhiet.md) | Vỏ, nhiệt, ăng-ten, cổng USB-C ngoài trời |
| [07-ke-hoach-phat-trien.md](docs/07-ke-hoach-phat-trien.md) | Các giai đoạn và cổng kiểm soát |
| [08-kiem-chung.md](docs/08-kiem-chung.md) | Kế hoạch đo và kiểm tra |
| [09-san-xuat.md](docs/09-san-xuat.md) | DFM, DFT, chứng nhận, chuỗi cung ứng |
| [10-rui-ro.md](docs/10-rui-ro.md) | Sổ rủi ro |
| [11-nhat-ky-quyet-dinh.md](docs/11-nhat-ky-quyet-dinh.md) | Quyết định đã chốt, đề xuất và câu hỏi mở |
| [12-bai-hoc-tu-cam4g.md](docs/12-bai-hoc-tu-cam4g.md) | Bài học rút ra từ dự án CAM4G và từ bản nháp v0.1 |
| [13-tinh-kha-thi.md](docs/13-tinh-kha-thi.md) | **Phân tích khả thi**: số liệu kiểm lại, lỗi thiết kế, chi phí, tiến độ, điều kiện dừng |
| [14-kien-truc-phan-mem.md](docs/14-kien-truc-phan-mem.md) | Kiến trúc phần mềm, hợp đồng module, phân vùng lưu trữ |
| [15-giao-thuc-va-cloud.md](docs/15-giao-thuc-va-cloud.md) | Giao thức I2C, kênh đánh thức, MQTT, WebRTC, OTA, bảo mật |
| [16-van-hanh.md](docs/16-van-hanh.md) | Cấp phát thiết bị, systemd, gỡ lỗi hiện trường, quy trình đo |
| [17-san-sang-prototype.md](docs/17-san-sang-prototype.md) | Điều kiện hoàn thành và biên bản tự kiểm tra 3 vòng |
| [18-tai-lieu-linh-kien.md](docs/18-tai-lieu-linh-kien.md) | Sổ linh kiện, đối chiếu datasheet với thiết kế, 1 giả định PACK |
| [19-truoc-khi-mua.md](docs/19-truoc-khi-mua.md) | Tài liệu và phân tích còn thiếu theo từng cổng trước khi mua/thử |

Bảng sinh tự động: [regmap](spec/generated/regmap.md) · [pinout J_B2B](spec/generated/b2b.md) · [MQTT](spec/generated/mqtt.md) · [JSON schema](spec/generated/mqtt.schema.json).

## Cảnh báo

Đây **không phải** sản phẩm đã kiểm chứng. Chưa có phép đo nào; chưa có board nào được đặt. Đọc [13](docs/13-tinh-kha-thi.md) trước khi dùng bất kỳ con số nào trong repo này để quyết định chi tiền.
