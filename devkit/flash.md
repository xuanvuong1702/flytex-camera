# Flash image và cài app

## 1. Image

1. Vào trang tải Luckfox cho đúng board (Pico Ultra / Core1106D dev board).
2. Tải image Linux có driver camera SC3336 và USB host.
3. Ghi bằng balenaEtcher/Rufus nếu boot từ SD; hoặc dùng tool Luckfox nếu eMMC.
4. Cắm USB-TTL, mở PuTTY/Tera Term 115200 8N1, giữ nút boot nếu cần.

## 2. Boot lần đầu

```sh
uname -a
cat /etc/os-release
ip addr
dmesg | tail -50
```

Đặt IP tĩnh hoặc DHCP reservation; ghi lại IP.

## 3. Copy app

Từ PC:

```powershell
scp -r app root@<IP>:/opt/flytex/
scp -r devkit root@<IP>:/opt/flytex/
```

Trên board:

```sh
cd /opt/flytex
python3 --version
python3 -m flytex.cli selftest
python3 devkit/scripts/devkit_check.py
```

## 4. Config

```sh
mkdir -p /data
cp devkit/config/devkit.json /data/config.json
# sửa mqtt_host, apn, relay_url
python3 - <<'PY'
from flytex.config import Config
c=Config.load('/data/config.json')
print(c)
PY
```

## 5. Systemd

```sh
cp devkit/systemd/flytex-device.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now flytex-device
journalctl -u flytex-device -f
```

Lưu ý: `run` cần MCU I2C + RK MPI; devkit chưa có MCU. Dùng `sim` và `feature_test` để test logic; chỉ bật service sau khi có adapter/board PWR.
