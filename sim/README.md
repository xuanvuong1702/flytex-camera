# Mô phỏng end-to-end

Mô phỏng này **không viết lại** logic bằng Python. Nó nạp firmware C thật (biên dịch thành thư viện) qua ctypes, nối vào ứng dụng Linux thật, và thay phần cứng bằng modem giả + cloud giả.

```
Python scenario
   │  FfiMcuLink (I2C)
   ▼
firmware C thật  ──►  rail, IRQ, regmap, timer
   ▲
   │  chân giả (PIR, VBUS, SOC_READY, modem STATUS)
SocEmulator + SimClock
   │
   ▼
app/flytex (power, recorder, uplink, cloud, commands)
```

## Chạy

```powershell
python firmware/mcu/tests/build.py lib   # sinh thư viện firmware
python sim/run.py --scenario basic
python sim/run.py --scenario low-battery
python sim/run.py --scenario all
python sim/run.py --list
```

| Kịch bản | Kiểm gì |
|---|---|
| `basic` | PIR → ghi → về Eco → motion vào hàng đợi → live → ngủ |
| `low-battery` | Pin yếu: đóng file, gửi shutdown, MCU cắt rail |
| `watch-wake` | Watch: modem giữ rail, RI đánh thức, `WAKE_ALARM` |
| `watch-ri-off` | `WAKE_CHAN=off`: RI không đánh thức |
| `tickless-day` | 24 giờ không sự kiện: 8640 lần thức (lấy mẫu 10 s), không có tick 1 ms |

Kết quả: báo cáo JSON trong `sim/build/` và tóm tắt ASCII ra màn hình. Mã trả khác 0 nghĩa là một bất biến bị vi phạm.

## Các bất biến được kiểm

1. Ứng dụng đọc đúng `PROTO_VER` và từ chối khi sai major.
2. PIR làm MCU bật rail SoC; SoC báo `SOC_READY`; ứng dụng vào S2 và ghi clip.
3. Hết clip, hệ thống về **đúng chế độ ngủ đã cấu hình**, không luôn về Eco.
4. Sự kiện `motion` đến cloud qua hàng đợi bền, có `id` duy nhất; gửi lại không tạo bản trùng.
5. Lệnh `live.start` được ack và đưa hệ thống vào S3; hết giờ về S2 rồi ngủ.
6. Pin cạn: ứng dụng đóng file, gửi `shutdown`, báo MCU; MCU cắt rail và vào sinh tồn.
7. Trong 24 giờ không sự kiện, số lần vào STOP nhỏ (tickless), không có vòng polling 1 ms.
8. Không có ngoại lệ nào bị nuốt: mọi lỗi mô phỏng đều làm kịch bản thất bại.

## Giới hạn

- Chưa có camera thật, chưa có video thật: nguồn hình là `FakeSource`.
- Chưa có MQTT TLS thật: `MemoryBus` thay broker.
- Chưa có modem thật: AT client chạy với transport giả.
- Thời gian mô phỏng nhanh hơn thời gian thực, nên không đo được công suất; công suất vẫn phải đo ở G0.
