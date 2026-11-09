# Khoảng cách tới “mua linh kiện, gắn, nạp phần mềm là chạy”

## 1. Định nghĩa

Có hai mức, đừng lẫn:

| Mức | Nghĩa | Trạng thái |
|---|---|---|
| **A. Devkit ghép dây** | Mua board có sẵn (Core1106D dev board, EVB modem, camera), cấp nguồn, nạp image, chạy app | Chưa có BSP/driver trên target; chưa có bộ dây/BOM devkit |
| **B. PCBA sản phẩm** | PCB riêng đã route, Gerber, PCBA, firmware release, test | **Chưa có PCB**; còn 12 nhóm việc |

Mức B là mức “gửi xưởng”. Hiện chưa đạt.

## 2. Việc còn lại cho PCBA

| # | Việc | Trạng thái | Ước lượng |
|---|---|---|---|
| W1 | 4 footprint cơ khí: B2B Samtec, Core1106D, service pad, TP1 | Thiếu | 1–2 ngày |
| W2 | Layout 4 lớp, route USB/MIPI/RF/nguồn, DRC/DFM, Gerber/drill/CPL | **Chưa có** | 2–4 tuần |
| W3 | Cơ khí/vỏ, anten, khe SIM, kính camera, seal IP | Chưa có | 2–3 tuần |
| W4 | Chọn nhà PCBA, DFM, test fixture, AOI/ICT | Chưa có | 1–2 tuần |
| W5 | Bring-up nguồn: M-02 tự tiêu, M-05 NTC, M-36 đỉnh modem, ILIM, nhiệt | Chưa đo | 1 tuần |
| W6 | Port STM32L0 trên target: NVM/temp/IWDG/RTC/STOP | Chỉ compile | 1–2 tuần |
| W7 | BSP Linux Core1106D: boot, eMMC, camera ISP, SD, USB, GPIO | Chưa có | 2–4 tuần |
| W8 | Modem EC200U: USB/PPP, RI, SMS, SIM, carrier | Chưa chạy | 1–2 tuần |
| W9 | App trên target: record/upload/OTA/cloud/power | Chỉ host + sim | 2–3 tuần |
| W10 | EMC/RF/thermal, tiếng ồn, dòng khởi động | Chưa có | 2–4 tuần |
| W11 | Độ tin cậy: mưa/nắng/nhiệt, cycle pin, treo modem | Chưa có | 4+ tuần |
| W12 | Chứng nhận: CE/RoHS, UN38.3/IEC 62133, nhà mạng | Thiếu hồ sơ | 4–8 tuần (ngoài) |

**Tổng cho PCBA:** tối thiểu **3–6 tháng** với 1–2 kỹ sư phần cứng + 1 kỹ sư embedded, chưa tính chứng nhận. Song song được W1–W4; W5–W9 phụ thuộc board.

## 3. Việc còn lại cho devkit ghép dây

Nếu mục tiêu chỉ là “cắm dây, nạp, chạy thử”:

| # | Việc | Ước lượng |
|---|---|---|
| D1 | Mua Core1106D dev board + camera SC3336 + EVB EC200U + nguồn 5 V/3 A | 3–7 ngày |
| D2 | Image Linux Luckfox + UART console + mạng | 2–3 ngày |
| D3 | App Python: camera record, upload, OTA, MQTT | 1–2 tuần |
| D4 | Modem: USB/PPP, AT, RI, SMS | 3–5 ngày |
| D5 | Nguồn: dùng module boost/buck rời + pack | 2–3 ngày |
| D6 | Đo công suất, nhiệt, log 24 h | 3–5 ngày |

**Tổng devkit:** **2–4 tuần** nếu board có sẵn, không cần PCB.

## 4. Đường ngắn nhất

1. **Tuần 1–2:** mua devkit, dựng image, chạy camera + modem + app trên bàn.
2. **Tuần 3–4:** đo nguồn/nhiệt, chốt mức tiêu thụ; sửa app.
3. **Tuần 5–8:** làm 4 footprint + layout PWR test board (2–4 lớp).
4. **Tuần 9–16:** layout board CMP + vỏ; đặt PCBA thử.
5. **Tuần 17–24:** bring-up, EMC/RF, độ tin cậy, chứng nhận.

## 5. Kết luận

- Để **“mua linh kiện rời gắn vào chạy ngay”**: hiện **chưa có PCB**, nên không thể. Còn **12 nhóm việc**, nặng nhất là layout/route và BSP Linux.
- Để **“mua devkit cắm dây chạy thử”**: còn **5–6 việc**, khoảng **2–4 tuần**.
- Không nên gộp: làm devkit trước để chốt firmware/power, rồi mới làm PCB; làm PCB trước khi firmware chạy sẽ phải sửa board nhiều lần.
