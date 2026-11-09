"""Sinh thư viện ký hiệu KiCad cho các IC nguồn từ bảng chân datasheet.

Nguồn chân:
- BQ25070: TI SLUSA66, Pin Functions (WSON-10 + PAD).
- TPS61088: TI SLVSCM8/SLVSE52, RHL VQFN-20 + PAD.
- TPS62840: TI SLVSEC6, DLC SON-8 + PAD.
- TPS22918: TI SLVSD76, DBV SOT-23-6.

    python -m hardware.kicad.symbols --write
    python -m hardware.kicad.symbols --check
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hardware" / "kicad" / "flytex-power.kicad_sym"
VERSION = "20251024"

LIB = "https://github.com/xuanvuong1702/flytex-camera"


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    kind: str = "passive"  # KiCad electrical type
    side: str = "left"


@dataclass(frozen=True)
class Part:
    name: str
    ref: str
    value: str
    datasheet: str
    pins: tuple[Pin, ...]
    footprint: str = ""


PARTS = (
    Part(
        "BQ25070",
        "U",
        "BQ25070",
        "https://www.ti.com/lit/ds/symlink/bq25070.pdf",
        (
            Pin("1", "IN", "power_in", "left"),
            Pin("2", "IMON", "output", "right"),
            Pin("3", "GND", "power_in", "left"),
            Pin("4", "LDO", "power_out", "right"),
            Pin("5", "TS", "input", "left"),
            Pin("6", "BAT", "passive", "right"),
            Pin("7", "CTRL", "input", "left"),
            Pin("8", "CHG", "open_collector", "right"),
            Pin("9", "GND", "power_in", "left"),
            Pin("10", "OUT", "power_out", "right"),
            Pin("11", "PAD", "power_in", "left"),
        ),
        "Package_SON:TI_DQC0010A",
    ),
    Part(
        "TPS61088",
        "U",
        "TPS61088",
        "https://www.ti.com/lit/ds/symlink/tps61088.pdf",
        (
            Pin("1", "VCC", "power_out", "right"),
            Pin("2", "EN", "input", "left"),
            Pin("3", "FSW", "input", "left"),
            Pin("4", "SW", "passive", "right"),
            Pin("5", "SW", "passive", "right"),
            Pin("6", "SW", "passive", "right"),
            Pin("7", "SW", "passive", "right"),
            Pin("8", "BOOT", "passive", "right"),
            Pin("9", "VIN", "power_in", "left"),
            Pin("10", "SS", "passive", "left"),
            Pin("11", "NC", "no_connect", "left"),
            Pin("12", "NC", "no_connect", "left"),
            Pin("13", "MODE", "input", "left"),
            Pin("14", "VOUT", "power_out", "right"),
            Pin("15", "VOUT", "passive", "right"),
            Pin("16", "VOUT", "passive", "right"),
            Pin("17", "FB", "input", "left"),
            Pin("18", "COMP", "passive", "right"),
            Pin("19", "ILIM", "passive", "right"),
            Pin("20", "AGND", "power_in", "left"),
            Pin("21", "PGND", "power_in", "left"),
        ),
        "Package_DFN_QFN:VQFN-20-1EP_3.5x3.5mm_P0.5mm_EP2.1x2.1mm",
    ),
    Part(
        "TPS62840",
        "U",
        "TPS62840",
        "https://www.ti.com/lit/ds/symlink/tps62840.pdf",
        (
            Pin("1", "GND", "power_in", "left"),
            Pin("2", "VIN", "power_in", "left"),
            Pin("3", "MODE", "input", "left"),
            Pin("4", "EN", "input", "left"),
            Pin("5", "VSET", "input", "right"),
            Pin("6", "STOP", "input", "left"),
            Pin("7", "SW", "passive", "right"),
            Pin("8", "VOS", "input", "right"),
            Pin("9", "PAD", "power_in", "left"),
        ),
        "Package_SON:TI_DLC0008A",
    ),
    Part(
        "TPS22918",
        "Q",
        "TPS22918",
        "https://www.ti.com/lit/ds/symlink/tps22918.pdf",
        (
            Pin("1", "VIN", "power_in", "left"),
            Pin("2", "GND", "power_in", "left"),
            Pin("3", "ON", "input", "left"),
            Pin("4", "CT", "passive", "right"),
            Pin("5", "QOD", "passive", "right"),
            Pin("6", "VOUT", "power_out", "right"),
        ),
        "Package_TO_SOT_SMD:SOT-23-6",
    ),
)


def _effects(size: float = 1.27, justify: str | None = None) -> str:
    just = f"\n\t\t\t\t(justify {justify})" if justify else ""
    return (
        "\n\t\t\t(effects\n"
        f"\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t)"
        f"{just}\n\t\t\t)"
    )


def _pin(pin: Pin, x: float, y: float, angle: int) -> str:
    return (
        f'\t\t(pin {pin.kind} line\n'
        f"\t\t\t(at {x:.3f} {y:.3f} {angle})\n"
        f"\t\t\t(length 5.08)\n"
        f'\t\t\t(name "{pin.name}"{_effects()}\n\t\t\t)\n'
        f'\t\t\t(number "{pin.number}"{_effects()}\n\t\t\t)\n'
        "\t\t)"
    )


def render_part(part: Part) -> str:
    rows = max(
        sum(1 for pin in part.pins if pin.side == "left"),
        sum(1 for pin in part.pins if pin.side == "right"),
    )
    height = max(10.16, (rows + 1) * 2.54)
    half_h = height / 2.0
    out = [
        f'\t(symbol "{part.name}"',
        "\t\t(pin_names\n\t\t\t(offset 0.508)\n\t\t)",
        "\t\t(exclude_from_sim no)",
        "\t\t(in_bom yes)",
        "\t\t(on_board yes)",
        f'\t\t(property "Reference" "{part.ref}"\n\t\t\t(at 0 {half_h + 2.54:.2f} 0)'
        f"{_effects(justify='left')}\n\t\t)",
        f'\t\t(property "Value" "{part.value}"\n\t\t\t(at 0 {-half_h - 1.27:.2f} 0)'
        f"{_effects()}\n\t\t)",
        f'\t\t(property "Footprint" "{part.footprint}"\n\t\t\t(at 0 0 0)'
        "\n\t\t\t(hide yes)" + f"{_effects()}\n\t\t)",
        f'\t\t(property "Datasheet" "{part.datasheet}"\n\t\t\t(at 0 0 0)'
        "\n\t\t\t(hide yes)" + f"{_effects()}\n\t\t)",
        f'\t\t(symbol "{part.name}_0_1"',
        f"\t\t\t(rectangle\n\t\t\t\t(start -7.62 {half_h:.2f})\n"
        f"\t\t\t\t(end 7.62 {-half_h:.2f})\n"
        "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)"
        "\n\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)",
        "\t\t)",
        f'\t\t(symbol "{part.name}_1_1"',
    ]
    left = [pin for pin in part.pins if pin.side == "left"]
    right = [pin for pin in part.pins if pin.side == "right"]
    step = 2.54
    for index, pin in enumerate(left):
        y = half_h - (index + 1) * step
        out.append(_pin(pin, -12.7, y, 0))
    for index, pin in enumerate(right):
        y = half_h - (index + 1) * step
        out.append(_pin(pin, 12.7, y, 180))
    out += ["\t\t)", "\t)"]
    return "\n".join(out)


def render() -> str:
    body = "\n".join(render_part(part) for part in PARTS)
    return (
        "(kicad_symbol_lib\n"
        f"\t(version {VERSION})\n"
        '\t(generator "flytex-symbols")\n'
        '\t(generator_version "10.0")\n'
        f"{body}\n"
        ")\n"
    )


def counts(text: str | None = None) -> dict[str, int]:
    text = text if text is not None else render()
    result: dict[str, int] = {}
    for part in PARTS:
        marker = f'(symbol "{part.name}"'
        start = text.index(marker)
        end = text.find('\n\t(symbol "', start + 1)
        chunk = text[start:end if end != -1 else len(text)]
        result[part.name] = chunk.count("\t\t(pin ")
    return result


def pin_table(part: Part) -> str:
    lines = [
        f"## {part.name}",
        "",
        f"- Datasheet: {part.datasheet}",
        f"- Footprint: `{part.footprint or 'chưa chọn'}`",
        "",
        "| Pin | Tên | Kiểu |",
        "|---|---|---|",
    ]
    for pin in part.pins:
        lines.append(f"| {pin.number} | {pin.name} | {pin.kind} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if current != text:
            print("file ký hiệu lệch nguồn; chạy --write", file=sys.stderr)
            return 1
        expected = {part.name: len(part.pins) for part in PARTS}
        if counts(text) != expected:
            print("số chân không khớp", file=sys.stderr)
            return 1
        print("OK: thư viện ký hiệu khớp nguồn")
        return 0
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8", newline="\n")
        table = "# Bảng chân IC nguồn (sinh tự động)\n\n" + "\n\n".join(
            pin_table(part) for part in PARTS
        )
        (OUT.parent / "pinout-power.md").write_text(
            table + "\n", encoding="utf-8", newline="\n"
        )
        print(f"ghi {OUT.relative_to(ROOT)}")
        return 0
    for name, count in counts(text).items():
        print(f"{name}: {count} chan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
