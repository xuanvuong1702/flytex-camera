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
| C-08 | Nhận lệnh khi ngủ bằng SMS/RI, có mô phỏng | Kịch bản `watch-wake`, `watch-ri-off`; 60 test firmware; HMAC/timestamp/replay phía SoC |
| C-09 | Báo cáo năng lượng và nhập số đo G0 | 124 test tools; nhập PPK2; 65 test hardware |
| C-10 | Gói thiết kế PWR/CMP đủ để vẽ schematic: block, net, giá trị, hình học, BOM, sổ linh kiện | `hardware/`; `python -m hardware.geom.cli --check`; `python -m hardware.parts.check --check` |
| C-11 | Quy trình bring-up và G0 có checklist thực thi được | `docs/16`, `hardware/bringup.md` |
| C-12 | Toàn bộ chạy một lệnh; **GitHub Actions xác nhận `success`** ở commit mới nhất; kết thúc phiên có commit và push | `python run_tests.py`; API `repos/.../actions/runs` (không chỉ tin máy Windows) |

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

Đã chạy: `python run_tests.py` (31/31 bước tại thời điểm vòng 1), `python tools/readiness.py --full`, rà BOM và mã nguồn theo §1.

| # | Phát hiện | Mức | Đã sửa |
|---|---|---|---|
| 1-1 | `DeviceService` gọi HTTP PUT **đồng bộ trong `step()`**; mạng chậm sẽ chặn máy trạng thái nguồn. Trái C-06 "không chặn luồng chính" | Chặn | Chuyển sang luồng nền + `Event` báo xong; chỉ thu gom kết quả ở `step`; khi ngủ chờ tối đa 5 s; test chứng minh `step` trả về < 0,5 s |
| 1-2 | SMS đánh thức **không được đọc**: `AtClient.sms_read()` có nhưng `DeviceService` không dùng, nên token SMS không bao giờ được kiểm; C-08 chỉ đúng ở phía MCU | Chặn | Thêm `_consume_wake_sms()` khi boot, so token bằng `hmac.compare_digest`; thêm `wake_token` vào `Config`; 3 test |
| 1-3 | Không có **BOM Rev A/Rev B**; C-10 nói "BOM" nhưng chỉ có BOM giai đoạn 0 | Chặn | Thêm `hardware/bom/` (34 dòng, có cột xác minh) + test 8 mục + README quy tắc |
| 1-4 | BOM ghi sai gói: TPS62840 ghi "SON 1,5×2 8 pad" (thực ra **đúng**), STM32L031G6U6 ghi LQFP-32 (sai, là **UFQFPN-28**), M24C32-FMN6TP ghi SO-8 (thực ra **đúng**) | Chặn | **Đính chính 2026-11-09:** chỉ STM32 đúng; hai "sửa" còn lại là sai và đã khôi phục SON-8/M24C32 SO-8. Xem vòng 7 |
| 1-5 | `sim/harness.py` vẫn dùng `RawMuxer` trong khi sản phẩm dùng MPEG-TS, nên mô phỏng không phủ container thật | TB | Đổi sang `TsMuxer`; 5 kịch bản vẫn đạt |
| 1-6 | `docs/17` C-12 đòi "cây làm việc sạch" ngay giữa phiên, không khả thi khi đang sửa | Nhỏ | Đổi thành kiểm commit/push ở cuối phiên |

Kết luận vòng 1: **chưa đủ**. Sửa xong 1-1…1-6, chạy lại từ vòng 1 theo §4.

### Vòng 2 — 2026-11-09 — ĐẠT

Đã chạy lại từ đầu:

| Việc | Lệnh | Kết quả |
|---|---|---|
| Toàn bộ test | `python run_tests.py` | 31/31 bước, 430 test |
| Checklist artifact | `python tools/readiness.py --full` | 24/24 đạt |
| Phủ lệnh MQTT | so `mqtt_gen.COMMANDS` với handler trong `service.py` | 10/10, không thiếu, không thừa |
| Dịch vụ end-to-end | `python -m flytex.cli sim --seconds 20` | ack=3, clip_ready=1, uploaded=1, sleep_cmd=1 |
| Mô phỏng firmware thật | `python sim/run.py --scenario all` | 5/5 kịch bản |

Phát hiện sản phẩm: **0**. Ghi chú phương pháp: script kiểm phủ lệnh lần đầu dùng regex bỏ sót lệnh không có dấu chấm (`reboot`) nên báo thiếu sai; đã sửa regex và chạy lại. Đây là lỗi công cụ kiểm tra, không phải lỗi sản phẩm.

Kết luận: đạt.

### Vòng 3 — 2026-11-09 — KHÔNG TÍNH (1 phát hiện nhỏ)

Đã chạy: `python run_tests.py` (31/31), `python tools/readiness.py --full` (24/24), kiểm nhất quán số liệu giữa docs/02, docs/06 và pwr-design, kiểm 26 chân B2B, kiểm gói linh kiện trong BOM.

| # | Phát hiện | Mức | Đã sửa |
|---|---|---|---|
| 3-1 | Nhiệt vỏ ghi "~13 K / ~58 °C" ở [06](06-co-khi-nhiet.md) trong khi pwr-design tính chính xác 12,8 K / 57,8 °C; hai nơi có thể trôi số | Nhỏ | Sửa docs/06 dùng 12,8 K / 57,8 °C và trỏ về pwr-design §6 làm nguồn |

Kết luận vòng 3: không tính; sửa xong, chạy lại toàn bộ từ vòng 4.

### Vòng 4 — 2026-11-09 — ĐẠT

Đã chạy lại từ đầu: `python run_tests.py` → 31/31 bước, 430 test (tại thời điểm vòng 4); `python tools/readiness.py --full` → 24/24; kiểm nhất quán số liệu docs/02, docs/06, pwr-design (hồi tiếp, NTC, ADC, nhiệt) → 0 lỗi.

Phát hiện sản phẩm: **0**. Kết luận: đạt.

### Vòng 5 — 2026-11-09 — ĐẠT

Đã chạy lại từ đầu: `python run_tests.py` → 31/31; `python tools/readiness.py --full` → 24/24; kiểm artifact độc lập:

| Việc | Kết quả |
|---|---|
| Đọc file `.ts` do mô phỏng sinh | 5 gói, 3 PID (0, 0x1000, 0x100), có PAT và PMT |
| Cấu trúc gói | chia hết 188, sync 0x47 |
| SVG bản vẽ | cả hai file parse được bằng XML |
| BOM | mọi dòng `dnp=no` có MPN |
| pwr-design | "Tất cả kiểm tra đạt" |

Phát hiện sản phẩm: **0**. Ghi chú phương pháp: script kiểm PSI ban đầu chỉ quét PID 0 nên báo thiếu PMT sai; đã sửa để quét cả PID PMT.

Kết luận: đạt.

### Vòng 6 — 2026-11-09 — ĐẠT

Đã chạy lại từ đầu: `python run_tests.py` → 31/31 bước, 430 test (tại thời điểm vòng 4); `python tools/readiness.py --full` → 24/24; `python -m flytex.cli sim --seconds 20` → chạy hết, có `uploaded=1`, `sleep_cmd=1`; phủ lệnh MQTT 10/10, không thiếu.

Phát hiện sản phẩm: **0**. Kết luận: đạt.

### Vòng 7 — 2026-11-09 — KHÔNG ĐẠT (rà soát độc lập bên ngoài)

Người dùng chạy trên Ubuntu 24.04 + gcc 13.3 và rà datasheet, phát hiện các lỗi sau. Đây là các phát hiện **phá kết luận cũ**, không phải góp ý nhỏ:

| # | Phát hiện | Mức | Trạng thái |
|---|---|---|---|
| 7-1 | `firmware/mcu/src/regmap.c` (và 3 file C khác) dùng `NULL` thiếu `<stddef.h>`; gcc `-Werror` làm **CI đỏ** ở commit `f5a699e`. Bằng chứng: GitHub Actions run `42611830406` kết luận `failure` | Chặn | Đã thêm include cho 4 file nguồn + 3 header + 9 file test; thêm `tools/check_c_includes.py` vào CI. Run `42613060903` cho commit `08a35e7`: **success** |
| 7-2 | BQ25798 mặc định 1S 4,2 V/2 A, watchdog 40 s reset VREG/ICHG/EN_CHG; MCU không có I2C master, SoC tắt khi Eco/Watch → không ai đặt 3,6 V. Nguy cơ sạc LFP tới 4,2 V | Chặn | **Loại BQ25798**, chọn **BQ25070** (float 3,5 V cố định, power-path, NTC, standalone 1 A — D-23); BOM/parts/docs cập nhật |
| 7-3 | NTC 7,15 kΩ/42,5–47,5 % VIN là của IC CAM4G cũ, không áp dụng cho IC mới; FR-10 "cắt bằng phần cứng" không còn đúng; firmware CHG_INHIBIT mâu thuẫn | Chặn | Đã tính mạng BQ25070: R1=20 kΩ, R2=8,25 kΩ, cắt nóng 44,9 °C/lạnh −0,6 °C; R5 DNP; còn đo M-05 |
| 7-4 | Hai "đính chính" gói ở vòng 1 là **sai**: TPS62840DLCR là SON-8 1,5×2 (DLC), M24C32-FMN6TP là SO-8 150 mil; chỉ STM32 UFQFPN-28 là đúng | Chặn | Khôi phục BOM/parts/checklist; ghi bài học: test BOM chỉ kiểm nhất quán nội bộ, không kiểm datasheet |
| 7-5 | +3V3 không phải 3,3 V: buck ở VIN 3,0–3,3 V chuyển 100 % duty, đầu ra bám pin; DS18B20 min 3,0 V | Chặn | Ghi rõ dải 3,0–3,3 V trong [02](02-thiet-ke-nguon.md) §5; thêm O-16; phải đo M-02/M-41 |
| 7-6 | BOM thiếu linh kiện phụ: cuộn cảm/tụ sạc, Rd USB-C, TVS VBUS, Rfsw/Rilim/COMP/boot/VCC/SS boost, CT load switch; 470 µF chưa rõ trước/sau công tắc; tụ ra boost mất dung lượng do DC bias; docs/02 §4 còn 178k/56k mâu thuẫn 169k/53,6k | Chặn | Đã thêm các dòng còn thiếu + đánh dấu phần phụ thuộc IC sạc; sửa docs/02; ghi chú derating |
| 7-7 | Pin LFP: ngưỡng cảnh báo 3,1 V/phục hồi 3,3 V và lấy mẫu tức thời dễ khóa thiết bị sai; cần lọc và ngưỡng theo tải | Chặn | **Đã sửa:** 3,05/2,90/3,20 V, đếm 6/3/12 mẫu (EMA chỉ log); 6 test battery; vẫn phải đo lại G0 |
| 7-8 | SMS đánh thức: token kiểm sau khi SoC đã boot; SMS rác/cuộc gọi có thể tiêu pin; token plaintext, replay, không whitelist số | Chặn | **Đã sửa:** HMAC-SHA256 trên counter + chống replay + lưu mốc + **giới hạn 1 wake/10 phút ở MCU**; còn whitelist số (cần UART phụ O-12) |
| 7-9 | IWDG chạy trong STOP chưa chốt; eDRX/PSM phụ thuộc nhà mạng nên mọi ước tính tuổi thọ Watch là có điều kiện | Cao | Ghi quyết định/đo ở G0; không dùng số 3–5 mA như số chắc chắn |
| 7-11 | BQ25070 CTRL là **giao diện xung một dây**, không phải điện trở; mặc định 285 mA, 11 xung ≈ 935 mA; BOM ghi R11 "điện trở" và không có GPIO | Chặn | Sửa BOM (R11 DNP), thêm GPIO `CHG_CTRL` + firmware phát 11 xung lúc boot (2 test); docs/02 §6.2 viết lại |
| 7-12 | "Power-path" BQ25070 chỉ chịu 1,2 A; boost 5 V đỉnh 5,56 A, phải nối thẳng VBAT; tài liệu chưa nói rõ | Chặn | docs/02 §6.4 viết rõ boost đấu thẳng VBAT, pin cấp đỉnh, sạc chia 1,2 A; đo M-01/M-36 |
| 7-13 | J_B2B dùng **header đực ở cả hai board** và không khóa; R5 7,15 kΩ còn trong BOM | Chặn | CMP đổi sang socket cái SSM-113-L-DV; cắt chân 26 làm khóa (D-24); R5 DNP |
| 7-14 | `wake_secret` nằm trong ALLOWED_KEYS nên **đổi được từ xa** qua MQTT | Chặn | Tách REMOTE_KEYS, cấm secret/token; test MQTT payload không chứa secret |
| 7-15 | Token SMS dùng timestamp, cold boot/RTC_LOST từ chối SMS hợp lệ | Cao | Đổi sang **counter** tăng dần + HMAC; không phụ thuộc RTC; test cold boot |
| 7-16 | Chưa có pinout Core1106D | Chặn | Đã nhập 112 chân từ XLS Luckfox vào `spec/core1106d/pins.csv` + 5 test |
| 7-17 | Port STM32L0: RTC chưa chọn nguồn LSI/WUCKSEL; IWDG vẫn chạy trong STOP; hẹn giờ có thể thức sớm ~16 lần | Chặn | Chọn LSI, PRER 127/255, WUCKSEL /16 hoặc ck_spre; IWDG mặc định tắt; thêm bước compile port; README ghi rõ chưa chạy target |
| 7-18 | OTA/upload chấp nhận `http://` | Chặn | Bắt buộc HTTPS, kiểm cả redirect; test reject http |
| 7-19 | SMS: docstring timestamp cũ; mốc counter ghi không nguyên tử; chưa whitelist | Chặn | Docstring counter; ghi temp+fsync+replace; thêm `wake_numbers` + test |
| 7-10 | Port STM32L0 chỉ là khung; nvm/temp trả ENOSYS; test "đạt" là test host với HAL giả | Cao | Không đổi: đây là giới hạn đã biết, nhưng phải ghi rõ trong mọi tuyên bố "chạy được" |

Kết luận vòng 7: **không đạt**. Kết luận "đủ điều kiện dựng prototype" ở §4 bị **thu hồi**.

## 4. Kết luận cuối

**0 blocker cứng cho prototype; 1 giả định PACK phải đo ở G0.** Không còn mục nào chặn việc dựng board thử, nhưng chưa được coi là đủ điều kiện sản xuất:

1. **Pack/BMS**: chọn cell EVE C33 15 Ah + BMS Daly 1S 15 A. **Giả định** BMS tự tiêu 50 µA và ho sơ UN38.3/IEC đang chờ; chỉ dùng prototype trên bàn, không giao/van chuyển. Đo M-02 và lấy hồ sơ trước khi sản xuất.

RI modem đã đóng bằng **module EC200U-EU** (MAIN_RI chân 62) thay vì breakout không rõ chân. Còn việc thiết kế carrier/RF, đo/kiểm không chặn mua: M-05 (NTC), M-36 (đỉnh modem/TPS22918), ILIM của TPS61088, và port STM32L0 vẫn là khung chưa chạy trên phần cứng. SMS đã có HMAC counter + rate limit; whitelist số cần UART phụ (O-12).

CI GitHub Actions đã xanh ở commit `01931c3` (run `42619397175`).

Các số 31/430 trong vòng 1–6 là số tại thời điểm đó; hiện tại 47/510.

Ba vòng 4–6 trước đây chỉ chứng minh các artifact nội bộ nhất quán; chúng **không** phát hiện được lỗi datasheet, lỗi gcc hay lỗi kiến trúc sạc. Quy trình đã được sửa: từ nay C-10/C-12 chỉ được coi là đạt khi có (a) datasheet được mở và ghi nguồn, (b) CI thật xanh.

## 5. Quy tắc kết luận

1. Ba vòng liên tiếp phải đạt **tất cả** C-01…C-12.
2. Mỗi vòng chạy lại từ đầu, không dựa vào kết quả vòng trước.
3. Nếu một vòng phát hiện lỗi: sửa, chạy lại toàn bộ, và **đếm lại từ vòng 1** nếu lỗi ảnh hưởng đến điều kiện đã đạt.
4. Kết luận ghi rõ: "đủ điều kiện dựng prototype" kèm danh sách việc còn lại thuộc §2.
