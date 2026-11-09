# Netlist pin-level CMP (sinh tự động)

- Nguồn: `hardware/netlist/cmp.py`; kiểm tra: `python -m hardware.netlist.cmp --check`.
- Camera SC3336 không có chân PWDN; chỉ RESET + XCLK + I2C + MIPI.

## 1. Linh kiện

| Ref | Giá trị | Footprint | Số chân |
|---|---|---|---|
| J1 | J_B2B 2x13 | Connector_Generic:Conn_02x13_Odd_Even | 15 |
| U1 | Core1106D1408 | flytex:Core1106D | 43 |
| J2 | SC3336 3MP (B) | Connector_FPC:FH12-20S-0.5SH | 20 |
| J3 | EC200U carrier | Connector_PinHeader_2.54mm:PinHeader_2x09_P2.54mm_Vertical | 18 |
| J4 | microSD | Connector_Card:microSD_HC_Hirose_DM3AT | 9 |
| U2 | TS3USB221A | Package_DFN_QFN:UQFN-10_1.4x1.8mm_P0.4mm | 10 |
| J5 | UART console | Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical | 3 |
| J6 | Service pads | Connector_Generic:Conn_01x04 | 4 |
| TP1 | Test points | Connector_Generic:Conn_01x04 | 4 |
| R1 | 10k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| C1 | 470uF 10V | Capacitor_SMD:CP_Elec_8x10 | 2 |
| C2 | 100nF | Capacitor_SMD:C_0603_1608Metric | 2 |
| R14 | 100k 1% | Resistor_SMD:R_0603_1608Metric | 2 |
| R15 | 100k 1% | Resistor_SMD:R_0603_1608Metric | 2 |

## 2. Net

- **+3V3** (9): J1.1, U1.76, U1.78, J2.19, J2.20, J4.4, U2.10, J5.1, C2.1
- **+5V_MODEM** (3): J1.3, J3.1, J3.2
- **+5V_SOC** (6): J1.2, U1.79, U1.80, U1.81, C1.1, R14.1
- **CAM_MCLK** (2): U1.58, J2.2
- **CAM_RST** (2): U1.60, J2.16
- **CAM_SCL** (2): U1.68, J2.13
- **CAM_SDA** (2): U1.69, J2.14
- **GND** (39): J1.4, U1.21, U1.25, U1.28, U1.29, U1.36, U1.47, U1.55, U1.82, U1.83, U1.84, U1.89, U1.112, J2.1, J2.3, J2.6, J2.9, J2.12, J2.15, J2.17, J2.18, J3.3, J3.4, J3.13, J3.14, J3.15, J3.16, J3.17, J3.18, J4.6, U2.5, U2.6, J5.3, J6.3, J6.4, R1.2, C1.2, C2.2, R15.2
- **IRQ** (2): J1.10, TP1.2
- **MIPI_CLKN** (2): U1.9, J2.8
- **MIPI_CLKP** (2): U1.10, J2.7
- **MIPI_D0N** (2): U1.11, J2.5
- **MIPI_D0P** (2): U1.12, J2.4
- **MIPI_D1N** (2): U1.7, J2.11
- **MIPI_D1P** (2): U1.8, J2.10
- **MODEM_PWRKEY** (2): J1.13, J3.12
- **MODEM_RESET** (2): J1.12, J3.11
- **MODEM_STATUS** (2): J1.15, J3.10
- **MODEM_UART_RX** (2): U1.65, J3.7
- **MODEM_UART_TX** (2): U1.66, J3.8
- **MODEM_USB_DM** (2): J3.6, U2.2
- **MODEM_USB_DP** (2): J3.5, U2.1
- **RI** (3): J1.11, J3.9, TP1.4
- **SCL** (2): J1.6, U1.63
- **SDA** (2): J1.5, U1.64
- **SD_CLK** (2): U1.54, J4.5
- **SD_CMD** (2): U1.53, J4.3
- **SD_D0** (2): U1.49, J4.7
- **SD_D1** (2): U1.50, J4.8
- **SD_D2** (2): U1.51, J4.1
- **SD_D3** (2): U1.52, J4.2
- **SD_DET** (2): U1.48, J4.9
- **SOC_READY** (2): J1.9, TP1.1
- **SVC_USB_DM** (2): U2.4, J6.2
- **SVC_USB_DP** (2): U2.3, J6.1
- **UART_MCU_TX** (2): J1.7, U1.70
- **UART_SOC_TX** (3): J1.8, U1.71, J5.2
- **USB_DM** (2): U1.22, U2.7
- **USB_DP** (2): U1.23, U2.8
- **USB_SEL** (4): J1.14, U2.9, TP1.3, R1.1
- **USB_VBUSDET** (3): U1.24, R14.2, R15.1

## 3. Kiểm tra

- Số lỗi: **0**

- Mọi net >= 2 đầu; chân SoC/camera khớp tài liệu; không có PWDN giả.
