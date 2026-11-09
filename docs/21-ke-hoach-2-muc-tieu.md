# Kế hoạch 2 mục tiêu

## Mục tiêu A — Devkit chạy thử phần mềm (ưu tiên)

**Định nghĩa xong:** mua đúng BOM, cắm dây theo guide, nạp image, chạy `devkit_check` + `feature_test`, quay/upload/MQTT/SMS/OTA ở mức test được.

| Pha | Việc | Đầu ra | Thời gian |
|---|---|---|---|
| D0 | Chốt BOM, wiring, flash, config, systemd, test script | `devkit/` đầy đủ | **Xong trước khi mua** |
| D1 | Mua: Luckfox Pico Ultra + SC3336 + EVB EC200U + nguồn + USB-TTL + SIM/anten | kiện hàng | 3–7 ngày |
| D2 | Flash image Luckfox, console UART, mạng | board boot, SSH | 1 ngày |
| D3 | Cài app, config devkit, chạy `sim` + `feature_test` | app chạy, log sạch | 1–2 ngày |
| D4 | Camera: chụp/ghi 10 s qua `rkipc`/ffmpeg; kiểm file | clip .ts/.mp4 phát được | 1–2 ngày |
| D5 | Modem: USB/PPP, AT, SIM, sóng, SMS, RI (nếu EVB ra) | ping + SMS | 2–3 ngày |
| D6 | Upload/MQTT/OTA trên mạng thật; đo dòng 24 h | log + số đo | 2–3 ngày |

**Tổng: 2–4 tuần sau khi có hàng.** Không cần PCB.

## Mục tiêu B — PCBA sản phẩm

**Định nghĩa xong:** PCB đã route/DRC/Gerber, PCBA, firmware release, test fixture, chứng nhận.

| Pha | Việc | Gate |
|---|---|---|
| B1 | 4 footprint cơ khí + layout PWR, DRC/Gerber | fab_check PWR PASS |
| B2 | Layout CMP, RF/anten, vỏ, DRC/DFM | fab_check full PASS |
| B3 | Đặt PCBA PWR, bring-up M-02/M-05/M-36 | board PWR chạy |
| B4 | Đặt PCBA CMP, BSP Linux/camera/modem | board CMP chạy |
| B5 | App end-to-end, OTA, độ tin cậy | 30 ngày log |
| B6 | CE/RoHS, UN38.3/IEC | hồ sơ |

**Tổng: 3–6 tháng** (xem docs/20).

## Quy tắc

1. **Không mua linh kiện devkit trước khi D0 xong.** D0 là bộ `devkit/` này.
2. Devkit dùng board có sẵn; không hàn module Core1106D xuống PCB.
3. Chỉ chuyển sang B khi A đã chốt công suất, camera, modem và app.
4. Mọi số đo ghi vào `hardware/measure/` theo mẫu.
5. Không đưa `UN38.3/IEC` vào phần mềm; đó là điều kiện pack.

## Mua gì

Xem [devkit/bom.csv](../devkit/bom.csv). Tối thiểu:

- Luckfox Pico Ultra (RV1106) hoặc board Luckfox có camera FPC + USB host.
- Camera SC3336 3MP (đúng module B).
- EVB EC200U-EU (USB) + anten + SIM data.
- Nguồn USB-C 5 V/3 A, USB-TTL 3,3 V, hub có nguồn, thẻ microSD, đồng hồ đo dòng.

## Sau khi mua

```bash
cd /opt/flytex
python3 devkit/scripts/devkit_check.py
python3 devkit/scripts/feature_test.py --dry-run
python3 -m flytex.cli sim --seconds 20
```
