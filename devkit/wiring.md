# Đấu dây devkit — chi tiết

## 0. Điểm phải biết trước khi cắm

Luckfox Pico Ultra có **USB-C và USB-A dùng chung một cổng USB**, có chip chuyển mạch:

- Cắm nguồn/USB-C → USB chuyển sang **USB-C**.
- Không cấp USB-C → USB chuyển sang **USB-A** (dùng cho modem).

Vì vậy **không thể vừa cấp nguồn bằng USB-C vừa cắm modem vào USB-A**. Chọn một trong hai cách:

| Cách | Nguồn | Modem | Ghi chú |
|---|---|---|---|
| **A (khuyến nghị)** | PoE module hoặc 5 V DC vào header 5 V/GND | USB-A | USB-A hoạt động; cần nguồn 5 V đủ 3 A |
| B | USB-C 5 V | Không dùng USB-A | Chỉ test board/camera, không test 4G USB |
| C | USB-C + hub có nguồn | Không | Hub không giải quyết chuyển mạch; USB-A vẫn tắt |

Nguồn tham khảo: [Luckfox Pico Ultra USB](https://wiki.luckfox.com/Luckfox-Pico-Ultra/USB).

## 1. Sơ đồ tổng thể

```
5V/3A DC ──► header 5V/GND của Pico Ultra
                 │
                 ├── FPC 20 pin ──► SC3336
                 ├── USB-A ──► hub có nguồn ──► EC200U EVB (USB)
                 ├── UART2 debug ──► USB-TTL 3.3V ──► PC
                 └── Ethernet (tuỳ chọn) ──► router

EC200U EVB: SIM + anten LTE + nguồn 5V riêng (nếu EVB không tự lấy USB)
```

## 2. Bảng kết nối

| Từ | Đến | Loại dây | Ghi chú |
|---|---|---|---|
| Nguồn 5 V + | Pico `5V` | dây đỏ 20–22 AWG | Đo 5,0–5,2 V trước khi cắm |
| Nguồn 5 V − | Pico `GND` | dây đen 20–22 AWG | Nối GND trước |
| Pico `GND` | USB-TTL `GND` | dupont | Nối trước TX/RX |
| Pico `UART2_TX` | USB-TTL `RX` | dupont | 115200 8N1 |
| Pico `UART2_RX` | USB-TTL `TX` | dupont | Chỉ cần khi gõ lệnh |
| Pico FPC | SC3336 FPC | cáp FPC 20 pin | Đúng chiều, khóa latch |
| Pico USB-A | Hub USB-A | cáp USB 2.0 | Hub có nguồn |
| Hub | EC200U EVB USB | cáp USB 2.0 data | Không dùng cáp sạc |
| EVB SIM | SIM data | nano/micro SIM | Lắp trước khi cấp nguồn |
| EVB MAIN | Anten LTE | u.FL/SMA | Không bật khi không anten |
| EVB DC | 5 V/2 A | jack/dupont | Nếu EVB không tự cấp qua USB |

## 3. UART console

- Dùng **UART2 debug** (3 chân GND/TX/RX trên header debug), không nhầm với `UART3_TX_M0/RX_M0` trên header 40 pin.
- USB-TTL phải **3,3 V**, không dùng loại 5 V.
- Không nối chân 3V3 của USB-TTL vào board.
- Thứ tự: GND → TX/RX → mở terminal → cấp nguồn.
- Cấu hình: **115200 8N1**, không flow control.

Kiểm tra:

```sh
# trên PC
# mở PuTTY/Tera Term, 115200
# trên board sau khi boot
uname -a
cat /proc/cmdline
```

## 4. Camera SC3336

- Cáp FPC 20 pin, pitch 0,5 mm; tiếp xúc hướng đúng, khóa latch.
- Không cắm/rút FPC khi board đang cấp nguồn.
- Anten WiFi (nếu dùng bản W) giữ cách camera và anten LTE ≥20 mm.

Kiểm tra:

```sh
dmesg | grep -i -E 'sc3336|rkisp|mipi|csi'
ls /dev/video*
media-ctl -p 2>/dev/null | head -40
```

Nếu không thấy camera: kiểm FPC, image đúng board, driver SC3336.

## 5. Modem EC200U

### 5.1 SIM và anten

- Lắp SIM **trước** khi cấp nguồn EVB.
- Anten MAIN bắt buộc; anten DRX (nếu có) gắn thêm.
- Không bật modem khi anten tháo.

### 5.2 USB

- EVB USB → hub có nguồn → Pico USB-A.
- Kiểm tra:

```sh
lsusb
dmesg | tail -30
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

- Nếu EVB dùng USB-C: dùng cáp USB-C → USB-A data, không phải cáp sạc.
- Modem đỉnh có thể >1,5 A; hub phải có nguồn 5 V/2 A riêng.

### 5.3 Nguồn EVB

- Nếu EVB có jack DC: cấp 5 V/2 A riêng.
- Nếu EVB chỉ lấy nguồn từ USB: hub phải đủ dòng; không cấp qua USB-C của Pico.
- **GND chung** giữa EVB và Pico (qua USB hoặc dây GND), tránh vòng ground.

### 5.4 AT cơ bản

```sh
# thay /dev/ttyUSB0 bằng thiết bị thấy được
stty -F /dev/ttyUSB0 115200 raw -echo
cat /dev/ttyUSB0 &
printf 'AT\r\n' > /dev/ttyUSB0
printf 'AT+CPIN?\r\n' > /dev/ttyUSB0
printf 'AT+CSQ\r\n' > /dev/ttyUSB0
printf 'AT+COPS?\r\n' > /dev/ttyUSB0
```

Kỳ vọng: `OK`, `+CPIN: READY`, `+CSQ: ...`, nhà mạng.

### 5.5 RI / PWRKEY / RESET (tuỳ chọn)

- **PWRKEY**: nhấn giữ theo datasheet EVB để bật; nhiều EVB tự bật khi cấp USB.
- **RESET**: chỉ dùng khi treo; không thay nguồn.
- **RI**: nếu EVB có chân RI 1,8 V, cần level shifter 1,8→3,3 V trước khi vào GPIO Pico. Devkit giai đoạn 1 **không nối RI**, dùng USB/AT.

## 6. Nguồn và đo dòng

| Điểm đo | Dụng cụ | Kỳ vọng |
|---|---|---|
| 5 V vào Pico | đồng hồ vạn năng | 5,0–5,2 V |
| Dòng Pico khi boot | USB-C meter / shunt | 0,3–0,8 A |
| Dòng modem khi bật | meter trên nhánh EVB | đỉnh 1,5–2 A |
| Dòng tổng | nguồn bench | ≥3 A |

- Đặt meter nối tiếp **trước** khi cắm tải.
- Không đo bằng cách chập que đo.
- Dùng nguồn bench có giới hạn dòng 3 A khi thử lần đầu.

## 7. Thứ tự cấp nguồn

1. Nối GND chung.
2. Cắm USB-TTL, mở console.
3. Cấp 5 V cho Pico, chờ boot.
4. Cắm camera (nếu chưa cắm).
5. Cấp hub, cắm modem.
6. Lắp SIM/anten, bật modem.
7. Kiểm tra `lsusb`, `dmesg`, `ifconfig`.

## 8. Kiểm tra từng bước

```sh
# 1. board sống
uname -a

# 2. camera
ls /dev/video*

# 3. modem USB
lsusb
ls /dev/ttyUSB*

# 4. mạng
ip addr
ping -c 3 8.8.8.8

# 5. app
cd /opt/flytex
PYTHONPATH=app python3 -m flytex.cli selftest
PYTHONPATH=app python3 -m flytex.cli sim --seconds 5
python3 devkit/scripts/feature_test.py --dry-run
```

## 9. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| Không có console | TX/RX chưa chéo, GND chưa nối | Đổi TX/RX, kiểm GND |
| `lsusb` không thấy modem | USB-A bị tắt do cấp USB-C | Cấp nguồn qua 5V/PoE, bỏ USB-C |
| Modem reset liên tục | Hub thiếu dòng | Hub có nguồn 5V/2A |
| Không thấy `/dev/ttyUSB0` | Cáp sạc hoặc driver | Dùng cáp data, `dmesg` |
| Camera không nhận | FPC sai chiều/image sai | Kiểm FPC, image SC3336 |
| Board boot rồi tắt | Nguồn yếu/sụt áp | Đo 5V, dùng nguồn 3A |

## 10. An toàn

- Không cấp 5 V vào chân 3V3.
- Không tháo anten khi modem đang phát.
- Không để board trần trên bàn kim loại.
- Dùng kính bảo hộ khi hàn; devkit không cần hàn.
- Pin LiFePO4 chỉ dùng khi có BMS; giai đoạn devkit dùng nguồn bench.
