# 01 — Kiến trúc hệ thống

- Trạng thái: Dự thảo v0.1
- Ngày: 2026-11-09

## 1. Ba phần và một pack

| Phần | Vai trò | Loại |
|---|---|---|
| **PWR** — board nguồn và giám sát | USB-C, bộ sạc, boost 5 V, buck 3,3 V, MCU giám sát luôn bật, cảm biến PIR và 1-Wire, đầu đo dòng | Tự thiết kế |
| **CMP** — board compute | Module Core1106, camera FPC, microSD, UART console, header cắm modem | Tự thiết kế |
| **MDM** — breakout modem | EC200U-EU, SIM, ăng-ten u.FL | Module OEM |
| **Pack** | Cell LFP 1S, BMS, dây NTC | Mua sẵn |
| **Camera** | Module cảm biến có IR-CUT và LED IR tích hợp | Module OEM `[ĐỀ XUẤT]` |

`[ĐỀ XUẤT]` Cách chia này là quyết định D-04 trong [nhật ký quyết định](11-nhat-ky-quyet-dinh.md).

```
 USB-C 5V ──► ┌──────────────── PWR ────────────────────────────┐
              │ Bộ sạc LFP ──► VBAT ◄── Pack (BMS, NTC)          │
              │                  │                                │
              │                  ├─► Buck 3,3 V ──► +3V3          │
              │                  └─► Boost 5 V ──► +5V_BOOST      │
              │                         ├─ SW ─► +5V_SOC          │
              │                         └─ SW ─► +5V_MODEM        │
              │ MCU giám sát (luôn bật) ◄── PIR, 1-Wire, VBUS     │
              └───────────────────┬──────────────────────────────┘
                                  │  J_B2B (nguồn + I2C + IRQ + điều khiển modem)
              ┌───────────────────▼──────────────────────────────┐
              │ CMP: Core1106 ── FPC camera (MIPI)                │
              │        ├─ microSD, UART console                   │
              │        └─ USB host + UART ──► header ──► MDM      │
              └──────────────────────────────────────────────────┘
```

## 2. Vì sao tách

| | PWR | CMP | MDM |
|---|---|---|---|
| Dòng | Lớn (đỉnh vài ampe) | Trung bình | Đỉnh khoảng 0,5 A |
| Rủi ro chính | Layout boost, nhiệt | Chân mịn, MIPI | Nguồn, mức logic |
| Tốc độ đổi | Theo cỡ pin | Theo SoC và camera | Theo nhà cung cấp |
| Số lớp mục tiêu | Ít, đồng dày `[ĐỀ XUẤT]` | 4 lớp, impedance control | Không áp dụng |

Dự án CAM4G gộp tất cả vào một board và phải dùng track 0,15 mm cho cả đường 5,6 A (chi tiết ở [12](12-bai-hoc-tu-cam4g.md)). Tách ra cho phép mỗi board dùng luật layout phù hợp, và mỗi lần đặt chỉ sửa một board.

## 3. Trạng thái nguồn

| Trạng thái | Mô tả | SoC | Modem | Dòng chờ `[ƯỚC TÍNH]` |
|---|---|---|---|---|
| **S0 Eco** | Chỉ MCU, PIR, RTC | Tắt | Tắt | ~1 mA |
| **S1 Watch** | Modem giữ eDRX; SMS/RI đánh thức MCU, MCU bật SoC | Tắt | Bật, eDRX | 3–5 mA |
| **S2 Record** | Ghi cục bộ | Bật | Tắt | 1,4 W khi ghi |
| **S3 Live** | Ghi và truyền trực tiếp | Bật | Bật | 2,3 W, thêm IR về đêm |
| **SF Fault** | Lỗi nhiệt hoặc pin cạn | Tắt | Tắt | ~1 mA |

Ghi chú quan trọng: ở S1, **SoC tắt** nên không ai giữ được phiên MQTT. Kênh nhận lệnh là SMS + `MODEM_RI`, chi tiết ở [15](15-giao-thuc-va-cloud.md) §4. Bản nháp v0.1 ghi "eDRX + MQTT" là không hiện thực được khi SoC tắt ([13](13-tinh-kha-thi.md) F-02).

Sau khi hết clip (S2), hệ thống quay về chế độ ngủ đã cấu hình (Eco hoặc Watch), không mặc định về Eco. Chi tiết máy trạng thái ở [04](04-firmware.md) §3.2 và mã ở `app/flytex/power.py`.

## 4. Luồng dữ liệu

- **MCU ↔ SoC:** I2C (MCU là slave) cộng một đường ngắt `MCU_IRQ` để MCU báo sự kiện mà SoC không cần polling. Giao thức ở [15](15-giao-thuc-va-cloud.md) §2, số liệu sinh ở `spec/generated/regmap.md`.
- **SoC ↔ modem:** USB cho dữ liệu, UART cho lệnh AT `[ĐỀ XUẤT]` `[CHƯA XÁC MINH]`. Lý do ở [05](05-ket-noi-va-cloud.md) §1. Vì Core1106 chỉ có một cổng USB, cần mux hoặc phương án nạp dự phòng ([03](03-giao-dien.md) §4.1).
- **MCU ↔ modem:** MCU điều khiển PWRKEY, RESET, đọc STATUS và **RI** (đánh thức khi có SMS), vì MCU luôn sống.
- **Thiết bị ↔ cloud:** MQTT cho điều khiển và sự kiện; WebRTC/WHEP cho xem trực tiếp qua relay ([15](15-giao-thuc-va-cloud.md) §6).

## 5. Thiết kế cho production

Giữ ổn định giữa prototype và production:

- sơ đồ rail và giới hạn dòng ([03](03-giao-dien.md) §1);
- connector và tín hiệu giữa các board ([03](03-giao-dien.md) §2–4), sinh từ `spec/b2b.toml`;
- bản đồ thanh ghi I2C có số phiên bản ([03](03-giao-dien.md) §5, [15](15-giao-thuc-va-cloud.md) §2), sinh từ `spec/registers.toml`;
- lỗ bắt vít và vị trí tản nhiệt ([06](06-co-khi-nhiet.md));
- đường nạp dịch vụ (pad hoặc mux USB), để không phụ thuộc modem ([03](03-giao-dien.md) §4.1).

Được phép đổi sau prototype: chip sạc (tuyến tính sang xung, thêm power-path), module camera, breakout modem, việc gộp PWR và CMP thành một board.
