# Devkit — bộ chạy thử trước khi làm PCB

Mục tiêu: mua đúng danh sách, cắm dây, nạp image, chạy `sim` + test camera/modem/mạng.

## Đọc theo thứ tự

1. [bom.csv](bom.csv) — mua gì.
2. [wiring.md](wiring.md) — cắm dây.
3. [flash.md](flash.md) — nạp image/cài app.
4. [troubleshooting.md](troubleshooting.md) — lỗi thường gặp.
5. [../docs/21-ke-hoach-2-muc-tieu.md](../docs/21-ke-hoach-2-muc-tieu.md) — plan 2 mục tiêu.

## Kiểm tra trước khi mua

```bash
python3 devkit/scripts/devkit_check.py --dry-run
```

Phải **OK**. Đây là điều kiện “tài liệu/software sẵn sàng trước khi mua”.

## Sau khi cắm

```bash
python3 devkit/scripts/devkit_check.py
python3 devkit/scripts/feature_test.py --dry-run
python3 devkit/scripts/feature_test.py --sim
python3 devkit/scripts/feature_test.py --camera
python3 devkit/scripts/feature_test.py --modem /dev/ttyUSB0
python3 devkit/scripts/feature_test.py --network 8.8.8.8
```

## Cài lên board

```bash
scp -r app devkit root@<IP>:/opt/flytex/
ssh root@<IP>
cd /opt/flytex
sh devkit/scripts/provision.sh /opt/flytex /data
```

## Giới hạn

- `run` cần MCU I2C + RK MPI; devkit chưa có board PWR/MCU.
- `sim` test logic; camera/modem test độc lập.
- Muốn test full end-to-end phải có board PWR + firmware MCU.
