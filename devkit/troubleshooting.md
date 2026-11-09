# Troubleshooting devkit

## Không thấy /dev/ttyUSB0

- Cắm lại cáp USB data (không phải cáp sạc).
- `dmesg | tail -30` xem driver `option`/`usbserial`.
- Modem EVB có thể dùng `/dev/ttyACM0`.
- Cấp nguồn hub trước khi cắm modem.

## Không thấy /dev/video0

- Kiểm FPC đúng chiều, khóa latch.
- `dmesg | grep -i -E 'sc3336|rkisp|mipi'`.
- Image phải có driver SC3336; nếu không, đổi image Luckfox.

## Modem có USB nhưng không lên mạng

```sh
lsusb
mmcli -L 2>/dev/null || true
ip link
udhcpc -i usb0
```

- Kiểm SIM đã kích hoạt, APN đúng.
- Anten phải gắn trước khi bật modem.

## Board không boot

- Đo 5V tại board; dòng đủ 3A.
- USB-TTL GND nối trước; TX/RX chéo.
- Thử boot từ SD/eMMC đúng image.

## `sim` lỗi import

```sh
export PYTHONPATH=/opt/flytex/app
python3 -m flytex.cli selftest
```
