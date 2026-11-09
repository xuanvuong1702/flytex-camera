# Triển khai lên thiết bị

Thư mục này chứa tệp cấu hình để chép lên thiết bị khi có board. **Chưa được thử trên thiết bị thật.**

| Tệp | Đích trên thiết bị |
|---|---|
| `systemd/flytex-device.service` | `/etc/systemd/system/flytex-device.service` |

## Các bước

```sh
# 1. Chép mã ứng dụng (gói app/flytex) vào image hoặc /opt/flytex
# 2. Tạo người dùng không đặc quyền
adduser --system --group --no-create-home flytex
usermod -aG i2c,dialout flytex

# 3. Cấp phát định danh (xem docs/16 §2)
install -d -m 700 -o flytex -g flytex /data/identity
install -m 600 -o flytex -g flytex cert.pem key.pem ca.pem /data/identity/
install -m 600 -o flytex -g flytex config.json /data/config.json

# 4. Cài dịch vụ
install -m 644 flytex-device.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now flytex-device
journalctl -u flytex-device -f
```

## Kiểm tra sau khi cài

1. `systemctl status flytex-device` — đang chạy, không quay vòng restart.
2. Log có dòng boot với lý do reset và phiên bản giao thức.
3. MQTT nhận bản tin `status` retained.
4. Tắt nguồn đột ngột 10 lần, bật lại: không mất clip đã đóng, chỉ mục không hỏng.
5. Rút SIM: thiết bị không crash, hàng đợi giữ bản tin, cắm lại thì gửi.

## Chưa có

- Script cấp phát chứng chỉ tự động (cần CA và công cụ PKI; không dùng thư viện mạng ngoài).
- Image Buildroot có Python, xem R-27.
- Cấu hình mux USB và GPIO `USB_SEL` (chờ chốt O-13).
