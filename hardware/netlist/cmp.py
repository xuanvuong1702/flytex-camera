"""Netlist pin-level CMP: SoC, camera, modem carrier, USB mux, SD, B2B.

Chỉ dùng các chân đã có trong tài liệu:
- Core1106D: spec/core1106d/pins.csv
- Camera: spec/camera/sc3336-b.toml
- TS3USB221A: TI RSE 10-pin
- B2B: 14 net chính (26 chân đầy đủ ở spec/generated/b2b.md)

    python -m hardware.netlist.cmp --write
    python -m hardware.netlist.cmp --check
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "hardware" / "netlist"
MD = OUT_DIR / "cmp-netlist.md"
CSV = OUT_DIR / "cmp-netlist.csv"
PINS_CSV = ROOT / "spec" / "core1106d" / "pins.csv"
CAMERA = ROOT / "spec" / "camera" / "sc3336-b.toml"


@dataclass(frozen=True)
class Pin:
    num: str
    name: str
    net: str = ""


@dataclass(frozen=True)
class Component:
    ref: str
    value: str
    footprint: str
    pins: tuple[Pin, ...]


def comp(ref, value, footprint, pins):
    return Component(ref, value, footprint, tuple(Pin(*pin) for pin in pins))


COMPONENTS = (
    comp("J1", "J_B2B 2x13", "Connector_Generic:Conn_02x13_Odd_Even", [
        ("1", "+3V3", "+3V3"), ("2", "+5V_SOC", "+5V_SOC"),
        ("3", "+5V_MODEM", "+5V_MODEM"), ("4", "GND", "GND"),
        ("5", "SDA", "SDA"), ("6", "SCL", "SCL"),
        ("7", "UART_MCU_TX", "UART_MCU_TX"), ("8", "UART_SOC_TX", "UART_SOC_TX"),
        ("9", "SOC_READY", "SOC_READY"), ("10", "IRQ", "IRQ"),
        ("11", "RI", "RI"), ("12", "MODEM_RESET", "MODEM_RESET"),
        ("13", "MODEM_PWRKEY", "MODEM_PWRKEY"), ("14", "USB_SEL", "USB_SEL"),
        ("15", "MODEM_STATUS", "MODEM_STATUS"),
    ]),
    comp("U1", "Core1106D1408", "flytex:Core1106D", [
        ("22", "USB_N", "USB_DM"), ("23", "USB_P", "USB_DP"),
        ("24", "USB_VBUSDET", "USB_VBUSDET"),
        ("7", "MIPI_D1N", "MIPI_D1N"), ("8", "MIPI_D1P", "MIPI_D1P"),
        ("9", "MIPI_CK0N", "MIPI_CLKN"), ("10", "MIPI_CK0P", "MIPI_CLKP"),
        ("11", "MIPI_D0N", "MIPI_D0N"), ("12", "MIPI_D0P", "MIPI_D0P"),
        ("48", "SD_DET", "SD_DET"),
        ("49", "SD_D0", "SD_D0"), ("50", "SD_D1", "SD_D1"),
        ("51", "SD_D2", "SD_D2"), ("52", "SD_D3", "SD_D3"),
        ("53", "SD_CMD", "SD_CMD"), ("54", "SD_CLK", "SD_CLK"),
        ("58", "CAM_MCLK", "CAM_MCLK"),
        ("60", "CAM_RST", "CAM_RST"),
        ("63", "I2C1_SCL", "SCL"), ("64", "I2C1_SDA", "SDA"),
        ("65", "UART3_TX", "MODEM_UART_RX"), ("66", "UART3_RX", "MODEM_UART_TX"),
        ("68", "I2C0_SCL", "CAM_SCL"), ("69", "I2C0_SDA", "CAM_SDA"),
        ("70", "UART4_RX", "UART_MCU_TX"), ("71", "UART4_TX", "UART_SOC_TX"),
        ("76", "VCC3V3_RTC", "+3V3"), ("78", "VCC_3V3", "+3V3"),
        ("79", "VCC5V0_SYS", "+5V_SOC"), ("80", "VCC5V0_SYS", "+5V_SOC"),
        ("81", "VCC5V0_SYS", "+5V_SOC"),
        ("21", "GND", "GND"), ("25", "GND", "GND"), ("28", "GND", "GND"),
        ("29", "GND", "GND"), ("36", "GND", "GND"), ("47", "GND", "GND"),
        ("55", "GND", "GND"), ("82", "GND", "GND"), ("83", "GND", "GND"),
        ("84", "GND", "GND"), ("89", "GND", "GND"), ("112", "GND", "GND"),
    ]),
    comp("J2", "SC3336 3MP (B)", "Connector_FPC:FH12-20S-0.5SH", [
        ("1", "GND", "GND"), ("2", "XCLK", "CAM_MCLK"), ("3", "GND", "GND"),
        ("4", "MDP0", "MIPI_D0P"), ("5", "MDN0", "MIPI_D0N"), ("6", "GND", "GND"),
        ("7", "MCP", "MIPI_CLKP"), ("8", "MCN", "MIPI_CLKN"), ("9", "GND", "GND"),
        ("10", "MDP1", "MIPI_D1P"), ("11", "MDN1", "MIPI_D1N"), ("12", "GND", "GND"),
        ("13", "SIO-C", "CAM_SCL"), ("14", "SIO-D", "CAM_SDA"), ("15", "GND", "GND"),
        ("16", "RESET", "CAM_RST"), ("17", "GND", "GND"), ("18", "GND", "GND"),
        ("19", "+3.3V", "+3V3"), ("20", "+3.3V", "+3V3"),
    ]),
    comp("J3", "EC200U carrier", "Connector_Generic:Conn_02x09_Odd_Even", [
        ("1", "+5V_MODEM", "+5V_MODEM"), ("2", "+5V_MODEM", "+5V_MODEM"),
        ("3", "GND", "GND"), ("4", "GND", "GND"),
        ("5", "USB_DP", "MODEM_USB_DP"), ("6", "USB_DM", "MODEM_USB_DM"),
        ("7", "UART_RX", "MODEM_UART_RX"), ("8", "UART_TX", "MODEM_UART_TX"),
        ("9", "RI", "RI"), ("10", "STATUS", "MODEM_STATUS"),
        ("11", "RESET", "MODEM_RESET"), ("12", "PWRKEY", "MODEM_PWRKEY"),
        ("13", "GND", "GND"), ("14", "GND", "GND"),
        ("15", "GND", "GND"), ("16", "GND", "GND"),
        ("17", "GND", "GND"), ("18", "GND", "GND"),
    ]),
    comp("J4", "microSD", "Connector_Card:microSD_HC_Hirose_DM3AT", [
        ("1", "DAT2", "SD_D2"), ("2", "CD/DAT3", "SD_D3"), ("3", "CMD", "SD_CMD"),
        ("4", "VDD", "+3V3"), ("5", "CLK", "SD_CLK"), ("6", "VSS", "GND"),
        ("7", "DAT0", "SD_D0"), ("8", "DAT1", "SD_D1"), ("9", "CD", "SD_DET"),
    ]),
    comp("U2", "TS3USB221A", "Package_DFN_QFN:UQFN-10_1.4x1.8mm_P0.4mm", [
        ("1", "1D+", "MODEM_USB_DP"), ("2", "1D-", "MODEM_USB_DM"),
        ("3", "2D+", "SVC_USB_DP"), ("4", "2D-", "SVC_USB_DM"),
        ("5", "GND", "GND"), ("6", "OE", "GND"), ("7", "D-", "USB_DM"),
        ("8", "D+", "USB_DP"), ("9", "S", "USB_SEL"), ("10", "VCC", "+3V3"),
    ]),
    comp("J5", "UART console", "Connector_Generic:Conn_01x03", [
        ("1", "3V3", "+3V3"), ("2", "RX", "UART_SOC_TX"), ("3", "GND", "GND"),
    ]),
    comp("J6", "Service pads", "Connector_Generic:Conn_01x04", [
        ("1", "DP", "SVC_USB_DP"), ("2", "DM", "SVC_USB_DM"),
        ("3", "GND", "GND"), ("4", "GND", "GND"),
    ]),
    comp("J7", "Test points", "Connector_Generic:Conn_01x04", [
        ("1", "SOC_READY", "SOC_READY"), ("2", "IRQ", "IRQ"),
        ("3", "USB_SEL", "USB_SEL"), ("4", "RI", "RI"),
    ]),
    comp("R14", "100k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "+5V_SOC"), ("2", "BOT", "USB_VBUSDET"),
    ]),
    comp("R15", "100k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "USB_VBUSDET"), ("2", "BOT", "GND"),
    ]),
)

POWER_NETS = {"+3V3", "+5V_SOC", "+5V_MODEM"}


def _known_core_pins() -> set[str]:
    with PINS_CSV.open(encoding="utf-8", newline="") as handle:
        return {row["pin"] for row in csv.DictReader(handle)}


def _camera_pins() -> set[str]:
    with CAMERA.open("rb") as handle:
        data = tomllib.load(handle)
    return {str(pin["num"]) for pin in data["pins"]}


def validate() -> list[str]:
    issues: list[str] = []
    core = _known_core_pins()
    camera = _camera_pins()
    for component in COMPONENTS:
        numbers = [pin.num for pin in component.pins]
        if len(numbers) != len(set(numbers)):
            issues.append(f"{component.ref}: trung so chan")
        if component.ref == "U1":
            for number in numbers:
                if number not in core:
                    issues.append(f"U1: chan {number} khong co trong Core1106D")
        if component.ref == "J2":
            for number in numbers:
                if number not in camera:
                    issues.append(f"J2: chan {number} khong co trong camera")
    by_net: dict[str, list[tuple[Component, Pin]]] = defaultdict(list)
    for component in COMPONENTS:
        for pin in component.pins:
            if pin.net:
                by_net[pin.net].append((component, pin))
    for net, ends in sorted(by_net.items()):
        if len(ends) < 2:
            issues.append(f"net {net} chi co {len(ends)} dau")
    for net in POWER_NETS:
        if net not in by_net:
            issues.append(f"thieu rail {net}")
    if any(pin.name == "PWDN" for component in COMPONENTS for pin in component.pins):
        issues.append("camera SC3336 khong co chan PWDN")
    return issues


def rows() -> list[dict[str, str]]:
    result = []
    for component in COMPONENTS:
        for pin in component.pins:
            result.append({
                "ref": component.ref,
                "value": component.value,
                "footprint": component.footprint,
                "pin": pin.num,
                "pin_name": pin.name,
                "net": pin.net,
            })
    return result


def render_markdown() -> str:
    by_net: dict[str, list[tuple[Component, Pin]]] = defaultdict(list)
    for component in COMPONENTS:
        for pin in component.pins:
            if pin.net:
                by_net[pin.net].append((component, pin))
    out = [
        "# Netlist pin-level CMP (sinh tự động)",
        "",
        "- Nguồn: `hardware/netlist/cmp.py`; kiểm tra: `python -m hardware.netlist.cmp --check`.",
        "- Camera SC3336 không có chân PWDN; chỉ RESET + XCLK + I2C + MIPI.",
        "",
        "## 1. Linh kiện",
        "",
        "| Ref | Giá trị | Footprint | Số chân |",
        "|---|---|---|---|",
    ]
    for component in COMPONENTS:
        out.append(
            f"| {component.ref} | {component.value} | {component.footprint} | "
            f"{len(component.pins)} |"
        )
    out += ["", "## 2. Net", ""]
    for net, ends in sorted(by_net.items()):
        pins = ", ".join(f"{component.ref}.{pin.num}" for component, pin in ends)
        out.append(f"- **{net}** ({len(ends)}): {pins}")
    issues = validate()
    out += ["", "## 3. Kiểm tra", "", f"- Số lỗi: **{len(issues)}**", ""]
    for issue in issues:
        out.append(f"- FAIL: {issue}")
    if not issues:
        out.append("- Mọi net >= 2 đầu; chân SoC/camera khớp tài liệu; không có PWDN giả.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    issues = validate()
    if issues:
        for issue in issues:
            print(f"LOI: {issue}", file=sys.stderr)
        return 1
    if args.check:
        current = MD.read_text(encoding="utf-8") if MD.exists() else None
        if current != render_markdown():
            print("cmp-netlist.md lech nguon; chay --write", file=sys.stderr)
            return 1
        print("OK: netlist CMP hop le")
        return 0
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MD.write_text(render_markdown(), encoding="utf-8", newline="\n")
        with CSV.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
            writer.writeheader()
            writer.writerows(rows())
        print(f"ghi {MD.relative_to(ROOT)} va {CSV.relative_to(ROOT)}")
        return 0
    print(render_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
