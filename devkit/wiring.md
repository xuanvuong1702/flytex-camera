# Đấu dây devkit

## 1. Sơ đồ

```
USB-C 5V/3A ──► Luckfox Pico Ultra (USB-C power)
                     │
                     ├── FPC 20 pin ──► SC3336 camera
                     ├── USB host ──► hub có nguồn ──► EC200U EVB (USB)
                     ├── UART0 ──► USB-TTL 3.3V ──► PC (console)
                     └── Ethernet/WiFi ──► router

EC200U EVB: SIM + anten LTE
```

## 2. Bảng chân UART

| Luckfox | USB-TTL | Ghi chú |
|---|---|---|
| GND | GND | Nối trước |
| TX (debug) | RX | 115200 8N1 |
| RX (debug) | TX | Chỉ cần khi gõ lệnh |
| 3V3 | — | **Không** nối 3V3 của TTL vào board |

## 3. Camera

- Cắm FPC 20 pin, đúng chiều tiếp xúc; khóa latch.
- Không uốn FPC quá 90°.
- Kiểm `dmesg | grep -i sc3336` hoặc `media-ctl -p`.

## 4. Modem

- SIM vào EVB trước khi cấp nguồn.
- Anten LTE vào u.FL/SMA; không bật modem khi không có anten.
- USB EVB vào hub có nguồn (modem đỉnh 2 A).
- Nếu EVB có chân RI, đưa về GPIO board (3.3 V) — devkit có thể bỏ qua, dùng USB/AT.

## 5. Nguồn

- Đo áp tại đầu board: 5,0–5,2 V.
- Đo dòng khởi động: modem bật có thể vọt >1,5 A.
- Không cấp 5 V vào chân 3V3.

## 6. Thứ tự cấp nguồn

1. USB-TTL + console.
2. Nguồn board.
3. Camera.
4. Hub + modem sau khi board boot.
5. SIM/anten trước khi bật modem.
