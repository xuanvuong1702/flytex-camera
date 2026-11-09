# Netlist pin-level PWR (sinh tự động)

- Nguồn: `hardware/netlist/pwr.py`; kiểm tra: `python -m hardware.netlist.pwr --check`.
- Đây là netlist để vẽ schematic KiCad, chưa phải PCB.

## 1. Linh kiện

| Ref | Giá trị | Footprint | Số chân |
|---|---|---|---|
| J1 | USB-C 16P | Connector_USB:USB_C_Receptacle_USB2.0_16P | 6 |
| J2 | Pack LFP 15Ah | Connector_JST:JST_XT30PW-M | 3 |
| J3 | J_B2B 2x13 | Connector_Generic:Conn_02x13_Odd_Even | 4 |
| J4 | MCU interface | Connector_Generic:Conn_01x08 | 8 |
| U1 | BQ25070 | Package_SON:TI_DQC0010A | 11 |
| U2 | TPS61088 | Package_DFN_QFN:VQFN-20-1EP_3.5x3.5mm_P0.5mm_EP2.1x2.1mm | 21 |
| U3 | TPS62840 | Package_SON:TI_DLC0008A | 9 |
| Q1 | TPS22918 | Package_TO_SOT_SMD:SOT-23-6 | 6 |
| Q2 | TPS22918 | Package_TO_SOT_SMD:SOT-23-6 | 6 |
| L1 | 1.2uH Isat 9A | Inductor_SMD:L_Vishay_IHLP-2525 | 2 |
| L2 | 1.0uH 1A | Inductor_SMD:L_0603_1608Metric | 2 |
| R1 | 20.0k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R2 | 8.25k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R3 | 1k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R4 | 100k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R6 | 267k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R7 | 64.9k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R8 | 10.5k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R9 | 169k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R10 | 53.6k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R13 | 267k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| C1 | 10uF 25V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C2 | 100nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C3 | 10uF 10V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C4 | 1uF 16V | Capacitor_SMD:C_0603_1608Metric | 2 |
| C5 | 100nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C6 | 10nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C7 | 22uF 16V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C8 | 22uF 16V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C9 | 2.2nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C10 | 10uF 10V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C11 | 22uF 6.3V | Capacitor_SMD:C_1206_3216Metric | 2 |
| C12 | 10nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C13 | 470uF 10V | Capacitor_SMD:CP_Elec_8x10 | 2 |
| C14 | 10nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| C15 | 470uF 10V | Capacitor_SMD:CP_Elec_8x10 | 2 |

## 2. Net

- **+3V3** (6): J3.1, J4.6, U3.8, L2.2, R4.1, C11.1
- **+5V_BOOST** (8): U2.14, U2.15, U2.16, Q1.1, Q2.1, R9.1, C7.1, C8.1
- **+5V_MODEM** (4): J3.3, Q2.5, Q2.6, C15.1
- **+5V_SOC** (4): J3.2, Q1.5, Q1.6, C13.1
- **BOOT_BOOST** (2): U2.8, C5.1
- **CHG_CTRL** (2): J4.1, U1.7
- **CHG_STAT** (3): J4.2, U1.8, R4.2
- **COMP_BOOST** (3): U2.18, R8.1, C9.1
- **CT_MODEM** (2): Q2.4, C14.1
- **CT_SOC** (2): Q1.4, C12.1
- **EN_BOOST** (2): J4.3, U2.2
- **FB_BOOST** (3): U2.17, R9.2, R10.1
- **FSW_BOOST** (2): U2.3, R6.1
- **GND** (38): J1.A1, J1.B12, J2.2, J3.4, J4.7, U1.3, U1.9, U1.11, U2.11, U2.12, U2.20, U2.21, U3.1, U3.3, U3.6, U3.9, Q1.2, Q2.2, R2.2, R3.2, R7.2, R8.2, R10.2, R13.2, C1.2, C2.2, C3.2, C4.2, C6.2, C7.2, C8.2, C9.2, C10.2, C11.2, C12.2, C13.2, C14.2, C15.2
- **ILIM_BOOST** (2): U2.19, R7.1
- **IMON** (2): U1.2, R3.1
- **LDO** (3): U1.4, R1.1, C2.1
- **MODEM_PWR_EN** (2): J4.5, Q2.3
- **SOC_PWR_EN** (2): J4.4, Q1.3
- **SS_BOOST** (2): U2.10, C6.1
- **SW_BOOST** (7): U2.4, U2.5, U2.6, U2.7, L1.2, R6.2, C5.2
- **SW_BUCK** (2): U3.7, L2.1
- **TS** (4): J2.3, U1.5, R1.2, R2.1
- **VBAT** (10): J2.1, J4.8, U1.6, U1.10, U2.9, U3.2, U3.4, L1.1, C3.1, C10.1
- **VBUS** (4): J1.A4, J1.B9, U1.1, C1.1
- **VCC_BOOST** (2): U2.1, C4.1
- **VSET** (2): U3.5, R13.1

## 3. Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Số lỗi | 0 |
| Tất cả net >= 2 đầu, đủ rail, số chân khớp symbol | ĐẠT |
