# Sổ linh kiện và đối chiếu thiết kế (sinh tự động)

- Nguồn: `spec/parts.toml`; kiểm tra: `python -m hardware.parts.check --check`.
- `verified`: **yes** đã đối chiếu datasheet, **partial** mới một phần, **no** chưa mở datasheet.
- Kết quả: **2 blocker**, 3 cảnh báo. Blocker là việc phải đóng trước khi đặt hàng.

## 1. Linh kiện chính

| ID | MPN | Gói | Xác minh | Datasheet | Ghi chú |
|---|---|---|---|---|---|
| U1 | TPS61088RHLR | VQFN-20 | partial | https://www.ti.com/product/TPS61088 | Dung cho boost 5 V. Phai doi chieu Vref, fsw, ILIM va dieu kien nhiet. |
| U2 | TPS62840DLCR | SON-8 1.5x2 mm (DLC) | yes | https://www.ti.com/product/TPS62840 | Goi DLC = SON-8 1,5x2 (CAM4G dung). VSET=267 kΩ cho 3,3 V theo Table 1 datasheet TPS62840 trang 13; khong phai divider 2R. |
| U3 | BQ25070DQCR | WSON-10 (DQC) 3x2 mm | partial | https://www.ti.com/product/BQ25070 | Sac tuyen tinh LFP 1S 1 A, float 3,5 V co dinh, power-path, NTC, standalone. Doi tu BQ25798 vi mac dinh 4,2 V + watchdog. Can doc datasheet de tinh CTRL va mang NTC. |
| U4 | STM32L031G6U6 | UFQFPN-28 | partial | https://www.st.com/en/microcontrollers-microprocessors/stm32l031g6.html | Da sua goi tu LQFP-32 sang UFQFPN-28. Can kiem so chan GPIO va kha nang I2C slave. |
| U5 | M24C32-FMN6TP | SO-8 150 mil | yes | https://www.st.com/en/memories/m24c32-f.html | EEPROM cau hinh. MN = SO8 150 mil; dinh chinh lan 2: lan sua truoc sang TSSOP-8 la SAI. |
| Q1Q2 | TPS22918DBVR | SOT-23-6 | yes | https://www.ti.com/product/TPS22918 | Cong tac tai cho +5V_SOC va +5V_MODEM. |
| U6 | TS3USB221ARSER | UQFN-10 | partial | https://www.ti.com/product/TS3USB221A | Mux USB 2.0 cho modem va pad nap dich vu. Can kiem dong ro va ESD. |
| J1 | USB4085-GF-A | USB-C 16P | no | https://gct.co/connector/usb4085 | Receptacle USB-C thuong, CHUA phai loai chong nuoc. O-06 chua dong. |
| J2 | TSM-113-01-L-DV | 2x13 2.54 mm | partial | https://www.samtec.com/products/tsm-113-01-l-dv | J_B2B 26 chan. Can doi chieu ban ve co khi va chieu cao khi cap. |
| J3 | XT30PW-M | 2 pin | partial | https://www.amass.com/en/product/xt30 | Connector pack. Can kiem dong danh dinh va khoa chong nguoc. |
| L1 | IHLP2525CZER1R2M01 | 2525 | partial | https://www.vishay.com/en/product/34108/ | Cuon cam boost. Phai kiem Isat o 125 do C va DCR. |
| J4 | FH12-20S-0.5SH(55) | FPC 20 pin 0.5 mm | partial | https://www.hirose.com/product/series/FH12 | Connector FPC camera. Pinout phu thuoc module camera (O-02). |
| J5 | TSW-109-07-G-D | 2x9 2.54 mm | partial | https://www.samtec.com/products/tsw-109-07-g-d | Header modem tren CMP; phai khop breakout co RI. |
| J6 | DM3AT-SF-PEJM5 | microSD | partial | https://www.hirose.com/product/series/DM3 | Khe microSD; tiep can khi mo vo de nap du phong. |
| J7 | SSM-113-L-DV | 2x13 2.54 mm socket | partial | https://www.samtec.com/products/ssm-113-l-dv | Socket tren CMP de ghep voi header duc TSM tren PWR; cat chan 26 lam khoa. |

### Thông số then chốt

**U1 — TPS61088RHLR**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| vin_min_v | 2.7 | V | datasheet |
| vin_max_v | 12.0 | V | datasheet |
| vout_max_v | 12.6 | V | datasheet |
| iout_a | 3.0 | A | thiet ke |
| vref_v | 1.204 | V | datasheet |
| ilim_a | 8.47 | A | tinh theo Rilim |
| temp_min_c | -40 | C | datasheet |
| temp_max_c | 125 | C | datasheet |

**U2 — TPS62840DLCR**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| vin_min_v | 1.8 | V | datasheet |
| vin_max_v | 6.5 | V | datasheet |
| iout_a | 0.75 | A | datasheet |
| iq_ua | 0.06 | uA | datasheet (60 nA) |
| vref_v | 0.6 | V | CHUA XAC MINH |
| adjustable | True |  | VSET resistor |
| vset_ohm | 267000 | ohm | datasheet Table 1 |

**U3 — BQ25070DQCR**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| vin_min_v | 3.75 | V | datasheet |
| vin_max_v | 10.2 | V | datasheet |
| ichg_a | 0.935 | A | 11 xung CTRL |
| ichg_default_a | 0.285 | A | khong gui xung |
| ctrl_pulses | 11 | xung | bang 1 datasheet |
| ntc_r1_ohm | 20000 | ohm | tinh theo datasheet |
| ntc_r2_ohm | 8250 | ohm | tinh theo datasheet |
| ts_hot_c | 44.9 | C | tinh toan |
| ts_cold_c | -0.6 | C | tinh toan |
| vfloat_v | 3.5 | V | datasheet (co dinh) |
| power_path | True |  | datasheet |
| lfp_1s | True |  | datasheet |
| ntc | True |  | datasheet |
| standalone | True |  | datasheet |
| approved | True |  | chon cho prototype |

**U4 — STM32L031G6U6**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| stop_ua | 0.4 | uA | datasheet (typ, RTC tat) |
| gpio | 24 | chan | datasheet |
| temp_min_c | -40 | C | datasheet |
| temp_max_c | 85 | C | datasheet |
| i2c | True |  | datasheet |
| i2c_wakeup_stop | False |  | CHUA XAC MINH; thiet ke khong phu thuoc |

**U5 — M24C32-FMN6TP**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| vcc_min_v | 1.7 | V | datasheet |
| vcc_max_v | 5.5 | V | datasheet |
| i2c | True |  | datasheet |

**Q1Q2 — TPS22918DBVR**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| vin_max_v | 5.5 | V | datasheet |
| imax_a | 2.0 | A | datasheet |
| ron_mohm | 55 | mOhm | datasheet |

**U6 — TS3USB221ARSER**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| usb_hs | True |  | datasheet |
| channels | 2 | kenh | datasheet |
| vin_max_v | 3.6 | V | datasheet |

**J1 — USB4085-GF-A**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| waterproof | False |  | datasheet |
| current_a | 3.0 | A | datasheet |

**J2 — TSM-113-01-L-DV**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| pins | 26 | chan | datasheet |
| current_per_pin_a | 1.0 | A | CHUA XAC MINH |

**J3 — XT30PW-M**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| current_a | 15.0 | A | datasheet |

**L1 — IHLP2525CZER1R2M01**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| inductance_uh | 1.2 | uH | datasheet |
| isat_a | 9.0 | A | CHUA XAC MINH |

**J4 — FH12-20S-0.5SH(55)**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| pins | 20 | chan | datasheet |
| pitch_mm | 0.5 | mm | datasheet |

**J5 — TSW-109-07-G-D**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| pins | 18 | chan | datasheet |

**J6 — DM3AT-SF-PEJM5**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| pins | 8 | chan | datasheet |

**J7 — SSM-113-L-DV**

| Thông số | Giá trị | Đơn vị | Nguồn |
|---|---|---|---|
| pins | 26 | chan | datasheet |

## 2. Module ngoài BOM

| ID | Tên | Xác minh | Tài liệu | Ghi chú |
|---|---|---|---|---|
| MODEM | EC200U-EU breakout | partial | https://www.quectel.com/product/lte-ec200u-series | Can xac nhan RI ra header, dinh dong burst, va ho tro eDRX/PSM tren mang VN. |
| SOC | Core1106D1408 | partial | https://wiki.luckfox.com/Core1106D/Introduction/ | Da xac minh 1 cong USB, H.264, bien the eMMC; da nap 112 chan tu Core1106D-PinOut.xls vao spec/core1106d/pins.csv. |
| CAMERA | Module camera FPC 20 chan co IR-CUT | no | — | Da chon SC3336 3MP Camera (B); pinout 20 chan da nap vao spec/camera/. |
| PACK | Pack LFP 1S 15 Ah co BMS | no | — | CHUA CHON nha cung cap. Can UN38.3, IEC 62133, BMS <=100 uA, sac >=1,5 A, NTC. |

## 3. Vấn đề phát hiện

| Mức | Mục | Mô tả |
|---|---|---|
| blocker | MODEM | chua xac nhan breakout dua RI ra header - kenh Watch khong chay |
| blocker | PACK | chua co pack/BMS kem UN38.3, IEC 62133, tu tieu <=100 uA |
| warn | MODEM | dinh dong 2 A la gia dinh chua do; xac nhan bang M-36 |
| warn | J1 | USB-C chua phai loai chong nuoc (O-06) |
| warn | L1 | Isat 9 A chua xac minh o 125 do C |

## 4. Cách dùng

- `--strict` dùng làm cổng **trước khi đặt hàng**: còn blocker thì không đặt.
- `--check` chỉ kiểm cấu trúc và file sinh; không chặn CI vì thiếu linh kiện chưa mua.
- Khi mở datasheet và xác nhận một thông số: sửa `verified` và `source` trong `spec/parts.toml`, chạy `--write`.

