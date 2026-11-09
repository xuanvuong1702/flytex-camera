# 19 — Tài liệu còn thiếu trước khi mua và thử nghiệm

- Trạng thái: danh sách kiểm soát v1.0, ngày 2026-11-09
- Mục đích: trả lời "còn thiếu gì trước khi bỏ tiền mua và trước khi bật board".
- Quy ước: **Có** = đã có trong repo hoặc trong tay; **Thiếu** = phải làm trước cổng tương ứng.

## 1. Cổng A — trước khi đặt PCB

| # | Tài liệu / phân tích | Trạng thái | Bằng chứng hoặc việc phải làm |
|---|---|---|---|
| A1 | Sổ linh kiện + đối chiếu thiết kế | **Một phần** | [parts-register](../hardware/parts-register.md); còn 4 blocker, `--strict` cố ý fail |
| A2 | BOM có MPN, gói, trạng thái xác minh | **Có** | [hardware/bom](../hardware/bom/) |
| A3 | Schematic PWR/CMP | **Thiếu** | Vẽ trong KiCad từ block và net đã chốt ([03](03-giao-dien.md), [pwr-design](../hardware/pwr-design.md), [bom](../hardware/bom/)) |
| A4 | Thư viện symbol/footprint đã kiểm | **Thiếu** | Mỗi footprint từ datasheet + bản in 1:1; checklist [footprint-test](../hardware/footprint-test/checklist.md) |
| A5 | Netlist/ERC và đối chiếu schematic–BOM | **Thiếu** | Xuất netlist, ERC sạch, so từng net với BOM |
| A6 | Stackup và quy tắc layout | **Thiếu** | Chọn stackup nhà máy; ghi rõ lớp, đồng, trở kháng MIPI/USB |
| A7 | Bản vẽ cơ khí 2D có kích thước (board, lỗ, connector) | **Một phần** | Có [boards.md](../hardware/boards.md) + SVG; cần bản 2D/3D có dung sai cho nhà máy |
| A8 | Mô hình 3D board + vỏ để kiểm xung đột | **Thiếu** | Xuất STEP từ KiCad; kiểm camera, nắp, pin, ăng-ten |
| A9 | Bản vẽ vỏ, gioăng, cửa sổ camera/PIR, khoang pin | **Thiếu** | Chốt O-06/O-07 trước, vì vỏ phụ thuộc cổng USB-C và ăng-ten |
| A10 | Vùng cấm ăng-ten và vị trí u.FL | **Thiếu** | Vẽ keepout; đặt xa nguồn boost và vỏ kim loại |
| A11 | Phân tích nhiệt (tối thiểu bảng tính; tốt nhất FEA) | **Một phần** | Có tính xấp xỉ [pwr-design](../hardware/pwr-design.md) §6; chưa có FEA, chưa có nắng |
| A12 | Phân tích ổn định vòng boost/buck, quá độ tải modem | **Thiếu** | Bù COMP theo datasheet + đo Bode/step load trên board Rev A |
| A13 | Phân tích EMC sơ bộ (nguồn xung, USB, LTE) | **Thiếu** | Danh sách nguồn nhiễu, lọc, ferrite, thứ tự đo pre-scan |
| A14 | BOM báo giá và thời gian giao | **Thiếu** | Gửi BOM cho 2 nhà cung cấp, đối chiếu tồn kho, MOQ |
| A15 | Kế hoạch kiểm tra sản xuất (DFT) và jig | **Một phần** | Có test point trong [02](02-thiet-ke-nguon.md) §9; cần bản vẽ jig, kịch bản nạp/kiểm |
| A16 | IC sạc LFP float bằng phần cứng + mạch NTC | **Một phần** | Đã chọn BQ25070; còn tính CTRL 1 A và mạng NTC theo datasheet, cập nhật BOM |
| A17 | Linh kiện phụ cho sạc và bảo vệ | **Một phần** | BOM đã thêm cuộn cảm/tụ/Rd/TVS/COMP nhưng phần phụ thuộc IC sạc còn `not-chosen` |

**Điều kiện qua cổng A:** A1–A5, A8, A14, **A16** xong; A6–A7, A9–A10 có bản phát hành; A11–A13 có kế hoạch đo. A1 chỉ được coi là xong khi `--strict` hết blocker.

## 2. Cổng B — trước khi lắp ráp

| # | Tài liệu | Trạng thái | Ghi chú |
|---|---|---|---|
| B1 | Gerber, drill, CPL, IPC-D-356 | **Thiếu** | Xuất từ KiCad; kiểm bằng trình xem Gerber |
| B2 | Báo cáo DFM của nhà máy | **Thiếu** | Khoảng cách, annular ring, solder mask, panel |
| B3 | Bản vẽ lắp ráp (vị trí, phân cực, chân 1) | **Thiếu** | Từ CPL + ảnh 3D |
| B4 | Stencil và profile reflow | **Thiếu** | Nhà máy cung cấp; ghi vào hồ sơ |
| B5 | Danh sách DNP có chủ đích | **Một phần** | Có cột `dnp` trong BOM; cần bản vẽ đánh dấu |
| B6 | Kiểm tra hàng nhập (IQC) | **Thiếu** | Danh sách kiểm: mã, gói, số lượng, ẩm, chân 1 |
| B7 | Kế hoạch nạp firmware MCU/SoC và ghi serial | **Thiếu** | SWD cho MCU; SoC qua pad/mux hoặc SD; script ghi serial + chứng chỉ |
| B8 | Kế hoạch ESD và đóng gói | **Thiếu** | Bao bì, tiếp địa, nhãn |

**Điều kiện qua cổng B:** B1–B4 xong và được nhà máy xác nhận; B6–B7 có hướng dẫn một trang.

## 3. Cổng C — trước khi cấp nguồn lần đầu

| # | Tài liệu | Trạng thái | Ghi chú |
|---|---|---|---|
| C1 | Quy trình bring-up có điểm dừng | **Có** | [hardware/bringup.md](../hardware/bringup.md) |
| C2 | Bảng điện áp/dòng kỳ vọng từng rail | **Có** | [02](02-thiet-ke-nguon.md) §1, §4, §5; [pwr-design](../hardware/pwr-design.md) |
| C3 | Sơ đồ test point và điểm đo | **Có** | [02](02-thiet-ke-nguon.md) §9, [03](03-giao-dien.md) §2 |
| C4 | Kịch bản nạp firmware MCU đầu tiên | **Một phần** | Có SWD; cần file build và lệnh nạp cụ thể |
| C5 | Quy trình an toàn pin (không chập, giới hạn dòng) | **Có** | [bringup](../hardware/bringup.md) §0–1, [02](02-thiet-ke-nguon.md) §7 |

## 4. Cổng D — trước khi đo G0

| # | Tài liệu | Trạng thái | Ghi chú |
|---|---|---|---|
| D1 | Danh sách phép đo M-01…M-41 và tiêu chí | **Có** | [08](08-kiem-chung.md) |
| D2 | Công cụ nhập số đo + báo cáo | **Có** | `tools/measure`, `ppk2`, `report` |
| D3 | Kịch bản đo độ trễ WebRTC và băng thông ba mạng | **Thiếu** | Cần script đo và biểu mẫu ghi |
| D4 | Kịch bản thử eDRX/PSM và SMS trên ba mạng | **Thiếu** | Cần quy trình, SIM, số điện thoại, token |
| D5 | Lịch tủ sấy và thiết bị đo | **Thiếu** | Đặt phòng lab, checklist dụng cụ |
| D6 | Biểu mẫu ghi kết quả có người đo, dụng cụ | **Có** | CSV 11 cột, cột ghi chú |

## 5. Cổng E — trước khi chứng nhận / bán

| # | Tài liệu | Trạng thái |
|---|---|---|
| E1 | Danh mục quy chuẩn áp dụng tại Việt Nam | **Thiếu** (O-10, chưa xác minh) |
| E2 | Báo giá và lịch phòng thử nghiệm | **Thiếu** |
| E3 | UN38.3, IEC 62133 của pack | **Thiếu** (chưa chọn pack) |
| E4 | Hồ sơ EMC, RF, an toàn | **Thiếu** |
| E5 | Hướng dẫn sử dụng, nhãn cảnh báo nhiệt, xử lý pin | **Thiếu** |

## 6. Phân tích kỹ thuật còn thiếu

| Phân tích | Vì sao cần | Làm ở đâu |
|---|---|---|
| Nhiệt FEA/CFD trong vỏ, có nắng | Quyết định có phải giảm hiệu năng | Trước khi chốt vỏ (A9/A11) |
| Ổn định vòng và quá độ tải | Tránh reset khi modem phát | Rev A (M-08) |
| Toàn vẹn nguồn (PI) và nhiễu | Ảnh hưởng camera/MIPI | Layout CMP/Rev B |
| EMC pre-scan | Tránh quay lại layout | Trước G4 |
| FMEA thiết bị | Hệ thống hoá rủi ro ngoài sổ rủi ro | Trước G4 |
| MTBF/độ tin cậy | Kỳ vọng tuổi thọ | Trước lô thí điểm |
| Phối hợp trở kháng ăng-ten, keepout | Sóng yếu trong vỏ nhôm | Trước khi làm vỏ (A10) |
| Hồ sơ sạc LFP (CV/CC, nhiệt, cân bằng) | An toàn và tuổi thọ pin | Khi chốt IC sạc (A1/U3) |
| Thương lượng dòng USB-C | Thời gian sạc thực tế | Trước khi chốt sạc |
| Thử IP65 (nước, bụi) | Yêu cầu NFR-05 | G4 |

## 7. Thứ tự làm đề xuất (2 tuần tới)

1. Đóng 4 blocker trong [18](18-tai-lieu-linh-kien.md) §2.1 — VSET buck, RI modem, camera, pack.
2. Vẽ schematic PWR trước (đã có đủ giá trị), rồi CMP sau khi có pinout camera và chân module.
3. Làm thư viện footprint + board thử footprint (G1) trước khi đặt board thật.
4. Chốt vỏ/ăng-ten/USB-C song song, vì ba thứ này khoá lẫn nhau.
5. Chỉ sau đó mới gửi BOM báo giá và đặt PCB.

## 8. Bổ sung sau rà soát 2026-11-09

| Việc | Trạng thái | Ghi chú |
|---|---|---|
| CI GitHub Actions xanh | **Chưa** | Đã sửa thiếu `<stddef.h>` và thêm lint; chờ run mới |
| Gói linh kiện đúng datasheet | **Một phần** | Đã khôi phục TPS62840 SON-8, M24C32 SO-8; các gói khác vẫn cần đối chiếu bản vẽ |
| Ngưỡng pin LFP có lọc | **Thiếu** | Phải sửa firmware và test trước G0 |
| SMS wake có rate-limit/HMAC | **Thiếu** | Kế hoạch ở [04](04-firmware.md) §5 |
| Quyết định IWDG trong STOP | **Có (tạm)** | Tắt trước STOP, bật lại sau; đo M-02 |
