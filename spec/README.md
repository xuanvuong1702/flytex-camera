# spec — nguồn sự thật máy đọc được

Ba hợp đồng của dự án nằm ở đây, dạng TOML để git diff được và để không cần thư viện ngoài:

| File | Nội dung | Sinh ra |
|---|---|---|
| [registers.toml](registers.toml) | Regmap I2C MCU ↔ SoC, phiên bản 1.1 | `firmware/mcu/include/flytex/regs_gen.h`, `firmware/mcu/src/regs_gen.c`, `app/flytex/regs_gen.py`, [generated/regmap.md](generated/regmap.md) |
| [b2b.toml](b2b.toml) | Pinout J_B2B 26 chân PWR ↔ CMP, ngân sách dòng | [generated/b2b.md](generated/b2b.md), [generated/pinout_pwr_cmp.csv](generated/pinout_pwr_cmp.csv) |
| [mqtt.toml](mqtt.toml) | Chủ đề, phong bì, sự kiện, lệnh, ack | `app/flytex/mqtt_gen.py`, [generated/mqtt.md](generated/mqtt.md), [generated/mqtt.schema.json](generated/mqtt.schema.json) |

## Chạy

```powershell
python spec/generate.py           # ghi lại mọi file sinh
python spec/generate.py --check   # CI: lệch spec là lỗi
python spec/tests/test_spec.py    # kiểm tra spec và bộ sinh
```

## Quy tắc

1. **Không sửa file sinh bằng tay.** Sửa TOML rồi chạy lại bộ sinh.
2. **Chỉ thêm, không đổi nghĩa.** Thanh ghi mới phải thêm vào cuối vùng; đổi nghĩa thanh ghi cũ là tăng major của giao thức.
3. **Kiểm tra tự động khi sinh:**
   - địa chỉ thanh ghi không chồng, không vượt vùng;
   - `PROTO_VER` khớp major/minor;
   - mọi thanh ghi nhiều byte là big-endian;
   - bitfield nằm trong kích thước thanh ghi;
   - số chân B2B liên tục và khớp `pins_total`;
   - mọi net nguồn có yêu cầu dòng và đủ hệ số dư 1,25×;
   - tên sự kiện và lệnh MQTT không trùng, retained phải QoS ≥ 1.
4. **Số liệu dòng của B2B là cận trên thiết kế**, không phải số đo. Ghi rõ nguồn khi cập nhật; xem [docs/13](../docs/13-tinh-kha-thi.md) §4.

## Thêm một thanh ghi

```toml
[[regs]]
name = "NEW_REG"
addr = 0x18
access = "rw"
size = 1
reset = 0x00
desc = "Mô tả ngắn, nêu lý do và phiên bản thêm."
```

Sau đó tăng `[bus] proto_minor`, chạy bộ sinh, cập nhật tài liệu nếu cần, và thêm test cho thanh ghi mới.

## Thêm một lệnh MQTT

Thêm khối `[[commands]]` vào `mqtt.toml`. Kiểm tra:

- `args` khai báo đủ kiểu và `required`;
- lệnh có thật trong `app/flytex/commands.py`, nếu chưa thì trả `NOT_IMPLEMENTED` chứ không im lặng;
- cập nhật [docs/15](../docs/15-giao-thuc-va-cloud.md) nếu hành vi cần giải thích.

## Vì sao TOML

TOML có trong thư viện chuẩn (`tomllib`, Python 3.11+), cho phép chú thích, và không cần PyYAML — nghĩa là CI và máy phát triển không phải cài gì.
