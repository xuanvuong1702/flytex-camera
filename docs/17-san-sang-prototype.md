# 17 — Sẵn sàng dựng prototype

- Trạng thái: khung đánh giá v1.0
- Ngày: 2026-11-09

Mục tiêu của dự án: một người có repo này + linh kiện trong tay có thể dựng prototype chạy được (ghi hình, xem trực tiếp, nhận lệnh, ngủ sâu) mà không phải viết lại phần mềm hay đoán giao diện.

Tài liệu này định nghĩa **điều kiện hoàn thành** và là biên bản tự kiểm tra. Chỉ được kết luận "đủ điều kiện chạy thật" sau **ba vòng kiểm tra liên tiếp** đều đạt, mỗi vòng chạy lại toàn bộ bằng chứng và ghi lại phát hiện.

## 1. Điều kiện hoàn thành

| # | Điều kiện | Bằng chứng |
|---|---|---|
| C-01 | Giao diện giữa các board là nguồn sự thật máy đọc được, sinh mã | `python spec/generate.py --check`; 29 test spec |
| C-02 | Regmap MCU↔SoC hiện thực hai phía, có test | 59 test firmware; test MCU trong app |
| C-03 | Máy trạng thái nguồn chạy thật, về đúng chế độ ngủ, có bắt tay tắt máy | 5 kịch bản `sim/run.py --scenario all` |
| C-04 | Ghi hình ra container phát được, chịu mất điện, có vòng ghi | Test muxer + recorder; kiểm file bằng parser độc lập |
| C-05 | Sự kiện lên cloud qua hàng đợi bền, không trùng, không mất khi restart | Test uplink + service |
| C-06 | Clip tải lên kho qua HTTPS, có thử lại và không chặn luồng chính | Test uploader + service |
| C-07 | OTA an toàn: chỉ nhận image đúng chữ ký, có A/B và quay lui | Test OTA; không có chữ ký thì từ chối rõ ràng |
| C-08 | Nhận lệnh khi ngủ bằng SMS/RI, có mô phỏng | Kịch bản `watch-wake`, `watch-ri-off`; 59 test firmware |
| C-09 | Báo cáo năng lượng và nhập số đo G0 | 120 test tools; nhập PPK2; 46 test hardware |
| C-10 | Gói thiết kế PWR/CMP đủ để vẽ schematic: block, net, giá trị, hình học, BOM | `hardware/`; `python -m hardware.geom.cli --check` |
| C-11 | Quy trình bring-up và G0 có checklist thực thi được | `docs/16`, `hardware/bringup.md` |
| C-12 | Toàn bộ chạy một lệnh, CI xanh; kết thúc phiên có commit và push | `python run_tests.py`; `git log origin/master` (kiểm ở cuối phiên) |

## 2. Ngoài phạm vi có kiểm soát

Những việc **không thể** làm trong repo này, phải làm trên máy có phần mềm chuyên dụng hoặc có linh kiện:

| Việc | Vì sao | Ai làm |
|---|---|---|
| Gerber, file PCB | Cần KiCad và footprint đã kiểm bằng linh kiện thật | Kỹ sư phần cứng, sau G0/G1 |
| Symbol/footprint cho module Core1106D, EC200U, camera | Cần bản vẽ chân chính thức của nhà cung cấp | Người vẽ, đối chiếu datasheet |
| Đo công suất, nhiệt, độ trễ thật | Cần board và dụng cụ đo | G0 |
| Chứng nhận hợp quy | Cần phòng thử nghiệm | G5 |

Gói thiết kế trong repo phải đủ để người vẽ chuyển sang KiCad mà không phải quyết định lại giao diện, nguồn hay giá trị linh kiện.

## 3. Biên bản kiểm tra

Mỗi vòng ghi: ngày, các lệnh đã chạy, kết quả, phát hiện, việc đã sửa. Không được bỏ qua phát hiện nhỏ.

### Vòng 1 — 2026-11-09 — KHÔNG TÍNH (có phát hiện)

Đã chạy: `python run_tests.py` (31/31 bước), `python tools/readiness.py --full`, rà BOM và mã nguồn theo §1.

| # | Phát hiện | Mức | Đã sửa |
|---|---|---|---|
| 1-1 | `DeviceService` gọi HTTP PUT **đồng bộ trong `step()`**; mạng chậm sẽ chặn máy trạng thái nguồn. Trái C-06 "không chặn luồng chính" | Chặn | Chuyển sang luồng nền + `Event` báo xong; chỉ thu gom kết quả ở `step`; khi ngủ chờ tối đa 5 s; test chứng minh `step` trả về < 0,5 s |
| 1-2 | SMS đánh thức **không được đọc**: `AtClient.sms_read()` có nhưng `DeviceService` không dùng, nên token SMS không bao giờ được kiểm; C-08 chỉ đúng ở phía MCU | Chặn | Thêm `_consume_wake_sms()` khi boot, so token bằng `hmac.compare_digest`; thêm `wake_token` vào `Config`; 3 test |
| 1-3 | Không có **BOM Rev A/Rev B**; C-10 nói "BOM" nhưng chỉ có BOM giai đoạn 0 | Chặn | Thêm `hardware/bom/` (34 dòng, có cột xác minh) + test 8 mục + README quy tắc |
| 1-4 | BOM ghi sai gói: TPS62840 "SON 1,5×2 8 pad" nhưng mã `DLCR` là **SOT-563 6 chân**; STM32L031G6U6 ghi LQFP-32 nhưng là **UFQFPN-28**; M24C32-FMN6TP ghi SO-8 nhưng là **TSSOP-8** | Chặn | Sửa BOM; đính chính [02](02-thiet-ke-nguon.md) §5 và checklist footprint — đây đúng là loại lỗi CAM4G |
| 1-5 | `sim/harness.py` vẫn dùng `RawMuxer` trong khi sản phẩm dùng MPEG-TS, nên mô phỏng không phủ container thật | TB | Đổi sang `TsMuxer`; 5 kịch bản vẫn đạt |
| 1-6 | `docs/17` C-12 đòi "cây làm việc sạch" ngay giữa phiên, không khả thi khi đang sửa | Nhỏ | Đổi thành kiểm commit/push ở cuối phiên |

Kết luận vòng 1: **chưa đủ**. Sửa xong 1-1…1-6, chạy lại từ vòng 1 theo §4.

### Vòng 2 — chờ chạy

- Trạng thái: chờ.

### Vòng 3 — chờ chạy

- Trạng thái: chờ.

### Vòng 4 — chờ chạy

- Trạng thái: chờ.

## 4. Quy tắc kết luận

1. Ba vòng liên tiếp phải đạt **tất cả** C-01…C-12.
2. Mỗi vòng chạy lại từ đầu, không dựa vào kết quả vòng trước.
3. Nếu một vòng phát hiện lỗi: sửa, chạy lại toàn bộ, và **đếm lại từ vòng 1** nếu lỗi ảnh hưởng đến điều kiện đã đạt.
4. Kết luận ghi rõ: "đủ điều kiện dựng prototype" kèm danh sách việc còn lại thuộc §2.
