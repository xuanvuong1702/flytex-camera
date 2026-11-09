"""Netlist pin-level cho chuỗi nguồn PWR.

Đây là nguồn sự thật để vẽ schematic KiCad PWR. Mỗi linh kiện có ref, value và
các chân; chân không nối để net rỗng. ERC kiểm:
- số chân IC khớp thư viện ký hiệu;
- mọi net có >= 2 đầu;
- các rail bắt buộc có ít nhất một nguồn;
- không có hai nguồn khác nhau cùng đẩy một rail.

    python -m hardware.netlist.pwr --write
    python -m hardware.netlist.pwr --check
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "hardware" / "netlist"
MD = OUT_DIR / "pwr-netlist.md"
CSV = OUT_DIR / "pwr-netlist.csv"
BOM = ROOT / "hardware" / "bom" / "pwr-rev-a.csv"

POWER_NETS = {"VBUS", "VBAT", "+5V_BOOST", "+3V3", "+5V_SOC", "+5V_MODEM"}


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


def comp(ref: str, value: str, footprint: str, pins: list[tuple[str, str, str]]) -> Component:
    return Component(ref, value, footprint, tuple(Pin(*pin) for pin in pins))


COMPONENTS = (
    comp("J1", "USB-C 16P", "Connector_USB:USB_C_Receptacle_USB2.0_16P", [
        ("A4", "VBUS", "VBUS"), ("B9", "VBUS", "VBUS"),
        ("A1", "GND", "GND"), ("B12", "GND", "GND"),
        ("A5", "CC1", "CC1"), ("B5", "CC2", "CC2"),
    ]),
    comp("J3", "Pack LFP 15Ah", "Connector_AMASS:AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", [
        ("1", "BAT+", "VBAT"), ("2", "BAT-", "GND"), ("3", "NTC", "TS"),
    ]),
    comp("J2", "J_B2B 2x13", "Connector_Generic:Conn_02x13_Odd_Even", [
        ("1", "+3V3", "+3V3"), ("2", "+5V_SOC", "+5V_SOC"),
        ("3", "+5V_MODEM", "+5V_MODEM"), ("4", "GND", "GND"),
    ]),
    comp("J6", "MCU interface", "Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical", [
        ("1", "CHG_CTRL", "CHG_CTRL"), ("2", "CHG_STAT", "CHG_STAT"),
        ("3", "EN_BOOST", "EN_BOOST"), ("4", "SOC_PWR_EN", "SOC_PWR_EN"),
        ("5", "MODEM_PWR_EN", "MODEM_PWR_EN"), ("6", "+3V3", "+3V3"),
        ("7", "GND", "GND"), ("8", "VBAT", "VBAT"), ("9", "VBAT_ADC", "VBAT_ADC"),
    ]),
    comp("U3", "BQ25070", "Package_SON:TI_DQC0010A", [
        ("1", "IN", "VBUS"), ("2", "IMON", "IMON"), ("3", "GND", "GND"),
        ("4", "LDO", "LDO"), ("5", "TS", "TS"), ("6", "BAT", "VBAT"),
        ("7", "CTRL", "CHG_CTRL"), ("8", "CHG", "CHG_STAT"),
        ("9", "GND", "GND"), ("10", "OUT", "VBAT"), ("11", "PAD", "GND"),
    ]),
    comp("R3", "100k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "VBAT"), ("2", "BOT", "VBAT_ADC"),
    ]),
    comp("R4", "100k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "VBAT_ADC"), ("2", "BOT", "GND"),
    ]),
    comp("U1", "TPS61088", "Package_DFN_QFN:VQFN-20-1EP_3.5x3.5mm_P0.5mm_EP2.1x2.1mm", [
        ("1", "VCC", "VCC_BOOST"), ("2", "EN", "EN_BOOST"), ("3", "FSW", "FSW_BOOST"),
        ("4", "SW", "SW_BOOST"), ("5", "SW", "SW_BOOST"), ("6", "SW", "SW_BOOST"),
        ("7", "SW", "SW_BOOST"), ("8", "BOOT", "BOOT_BOOST"), ("9", "VIN", "VBAT"),
        ("10", "SS", "SS_BOOST"), ("11", "NC", "GND"), ("12", "NC", "GND"),
        ("13", "MODE", ""), ("14", "VOUT", "+5V_BOOST"), ("15", "VOUT", "+5V_BOOST"),
        ("16", "VOUT", "+5V_BOOST"), ("17", "FB", "FB_BOOST"),
        ("18", "COMP", "COMP_BOOST"), ("19", "ILIM", "ILIM_BOOST"),
        ("20", "AGND", "GND"), ("21", "PGND", "GND"),
    ]),
    comp("U2", "TPS62840", "Package_SON:TI_DLC0008A", [
        ("1", "GND", "GND"), ("2", "VIN", "VBAT"), ("3", "MODE", "GND"),
        ("4", "EN", "VBAT"), ("5", "VSET", "VSET"), ("6", "STOP", "GND"),
        ("7", "SW", "SW_BUCK"), ("8", "VOS", "+3V3"), ("9", "PAD", "GND"),
    ]),
    comp("Q1", "TPS22918", "Package_TO_SOT_SMD:SOT-23-6", [
        ("1", "VIN", "+5V_BOOST"), ("2", "GND", "GND"), ("3", "ON", "SOC_PWR_EN"),
        ("4", "CT", "CT_SOC"), ("5", "QOD", "+5V_SOC"), ("6", "VOUT", "+5V_SOC"),
    ]),
    comp("Q2", "TPS22918", "Package_TO_SOT_SMD:SOT-23-6", [
        ("1", "VIN", "+5V_BOOST"), ("2", "GND", "GND"), ("3", "ON", "MODEM_PWR_EN"),
        ("4", "CT", "CT_MODEM"), ("5", "QOD", "+5V_MODEM"), ("6", "VOUT", "+5V_MODEM"),
    ]),
    comp("L1", "1.2uH Isat 9A", "Inductor_SMD:L_Vishay_IHLP-2525", [
        ("1", "VIN", "VBAT"), ("2", "SW", "SW_BOOST"),
    ]),
    comp("L2", "1.0uH 1A", "Inductor_SMD:L_0603_1608Metric", [
        ("1", "SW", "SW_BUCK"), ("2", "VOUT", "+3V3"),
    ]),
    comp("R14", "20.0k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "LDO"), ("2", "BOT", "TS"),
    ]),
    comp("R15", "8.25k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "TS"), ("2", "BOT", "GND"),
    ]),
    comp("R17", "1k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "IMON"), ("2", "BOT", "GND"),
    ]),
    comp("R18", "100k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "+3V3"), ("2", "BOT", "CHG_STAT"),
    ]),
    comp("R9", "5.1k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "CC1"), ("2", "BOT", "GND"),
    ]),
    comp("R10", "5.1k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "CC2"), ("2", "BOT", "GND"),
    ]),
    comp("R6", "267k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "FSW_BOOST"), ("2", "BOT", "SW_BOOST"),
    ]),
    comp("R7", "64.9k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "ILIM_BOOST"), ("2", "BOT", "GND"),
    ]),
    comp("R8", "10.5k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "COMP_BOOST"), ("2", "BOT", "GND"),
    ]),
    comp("R1", "169k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "+5V_BOOST"), ("2", "BOT", "FB_BOOST"),
    ]),
    comp("R2", "53.6k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "FB_BOOST"), ("2", "BOT", "GND"),
    ]),
    comp("R13", "267k 1%", "Resistor_SMD:R_0603_1608Metric", [
        ("1", "TOP", "VSET"), ("2", "BOT", "GND"),
    ]),
    comp("C11", "10uF 25V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "VBUS"), ("2", "N", "GND"),
    ]),
    comp("C4", "100nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "LDO"), ("2", "N", "GND"),
    ]),
    comp("C1", "10uF 10V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "VBAT"), ("2", "N", "GND"),
    ]),
    comp("C7", "1uF 16V", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "VCC_BOOST"), ("2", "N", "GND"),
    ]),
    comp("C6", "100nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "BOOT_BOOST"), ("2", "N", "SW_BOOST"),
    ]),
    comp("C8", "10nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "SS_BOOST"), ("2", "N", "GND"),
    ]),
    comp("C2", "22uF 16V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "+5V_BOOST"), ("2", "N", "GND"),
    ]),
    comp("C17", "22uF 16V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "+5V_BOOST"), ("2", "N", "GND"),
    ]),
    comp("C5", "2.2nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "COMP_BOOST"), ("2", "N", "GND"),
    ]),
    comp("C13", "10uF 10V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "VBAT"), ("2", "N", "GND"),
    ]),
    comp("C14", "22uF 6.3V", "Capacitor_SMD:C_1206_3216Metric", [
        ("1", "P", "+3V3"), ("2", "N", "GND"),
    ]),
    comp("C9", "10nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "CT_SOC"), ("2", "N", "GND"),
    ]),
    comp("C15", "470uF 10V", "Capacitor_SMD:CP_Elec_8x10", [
        ("1", "P", "+5V_SOC"), ("2", "N", "GND"),
    ]),
    comp("C16", "10nF", "Capacitor_SMD:C_0603_1608Metric", [
        ("1", "P", "CT_MODEM"), ("2", "N", "GND"),
    ]),
    comp("C3", "470uF 10V", "Capacitor_SMD:CP_Elec_8x10", [
        ("1", "P", "+5V_MODEM"), ("2", "N", "GND"),
    ]),
)

# Số chân phải khớp hardware/kicad/flytex-power.kicad_sym.
EXPECTED_IC_PINS = {"U1": 21, "U2": 9, "U3": 11, "Q1": 6, "Q2": 6}


def nets() -> dict[str, list[tuple[Component, Pin]]]:
    result: dict[str, list[tuple[Component, Pin]]] = defaultdict(list)
    for component in COMPONENTS:
        for pin in component.pins:
            if pin.net:
                result[pin.net].append((component, pin))
    return dict(result)


def validate() -> list[str]:
    issues: list[str] = []
    refs = [component.ref for component in COMPONENTS]
    if len(refs) != len(set(refs)):
        issues.append("trung ref")
    for component in COMPONENTS:
        numbers = [pin.num for pin in component.pins]
        if len(numbers) != len(set(numbers)):
            issues.append(f"{component.ref}: trung so chan")
        if component.ref in EXPECTED_IC_PINS:
            if len(component.pins) != EXPECTED_IC_PINS[component.ref]:
                issues.append(f"{component.ref}: so chan khong khop symbol")
    by_net = nets()
    for net, ends in sorted(by_net.items()):
        if len(ends) < 2:
            issues.append(f"net {net} chi co {len(ends)} dau")
    for net in POWER_NETS:
        if net not in by_net:
            issues.append(f"thieu rail {net}")
    bom_refs = set()
    with BOM.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            bom_refs.add(row["ref"])
    for component in COMPONENTS:
        if component.ref not in bom_refs:
            issues.append(f"{component.ref} khong co trong BOM PWR")
    sources = {
        "+5V_BOOST": ("U1",),
        "+3V3": ("U2",),
        "+5V_SOC": ("Q1",),
        "+5V_MODEM": ("Q2",),
        "VBAT": ("U3", "J3"),
    }
    for net, allowed in sources.items():
        refs_on_net = {component.ref for component, _ in by_net.get(net, [])}
        if not refs_on_net & set(allowed):
            issues.append(f"rail {net} khong co nguon {allowed}")
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
    by_net = nets()
    out = [
        "# Netlist pin-level PWR (sinh tự động)",
        "",
        "- Nguồn: `hardware/netlist/pwr.py`; kiểm tra: `python -m hardware.netlist.pwr --check`.",
        "- Đây là netlist để vẽ schematic KiCad, chưa phải PCB.",
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
    out += [
        "",
        "## 3. Kiểm tra",
        "",
        "| Kiểm tra | Kết quả |",
        "|---|---|",
    ]
    issues = validate()
    out.append(f"| Số lỗi | {len(issues)} |")
    if issues:
        for issue in issues:
            out.append(f"| {issue} | FAIL |")
    else:
        out.append("| Tất cả net >= 2 đầu, đủ rail, số chân khớp symbol | ĐẠT |")
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
            print("netlist.md lech nguon; chay --write", file=sys.stderr)
            return 1
        print("OK: netlist PWR hop le")
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
