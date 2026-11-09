# Gói sản xuất — trạng thái

**Chưa gửi xưởng.** Bản vẽ hiện có đủ để review kết nối, nhưng chưa phải gói fab.

Kiểm tra:

```
python tools/fab_check.py --check
```

| Hạng mục | Trạng thái |
|---|---|
| Schematic PWR/CMP | Có, ERC 0 |
| BOM | Có |
| PCB layout | **Thiếu** |
| Gerber/drill | **Thiếu** |
| CPL/pos | **Thiếu** |
| DRC report | **Thiếu** |
| Stackup | **Thiếu** |
| Footprint thật | **Thiếu 5**: B2B PWR (J2), B2B CMP (J1), Core1106D (U1), service pad (J6), test point 4 chân (TP1) |

## Việc bắt buộc trước khi gửi

1. Tạo footprint cơ khí: Samtec SSM-113-L-DV (socket B2B), TSM-113 header, Core1106D 112-pin 30×30, FPC 20-pin nếu chưa khớp, service pad, test point 4 chân.
2. Import netlist vào PCB, đặt linh kiện, route toàn bộ; đặc biệt USB, MIPI, RF modem, đường nguồn.
3. Stackup 4 lớp + trở kháng USB/MIPI; DRC/DFM; kiểm tra khoảng cách.
4. Xuất Gerber, drill, CPL, BOM, assembly drawing.
5. Kiểm tra Gerber bằng viewer; ký DFM với xưởng.
6. Test plan bring-up (docs/16) + test point.

Không được gửi khi `fab_check` còn THIẾU. Một board chưa route hoặc sai footprint sẽ không test được và tốn tiền oan.
