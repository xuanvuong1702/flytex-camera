"""Sinh schematic KiCad đầy đủ cho PWR và CMP.

Mỗi linh kiện (IC, R/C/L, connector) được đặt trên sheet; mỗi chân có global
label đúng tên net trong netlist. Cách này giữ connectivity theo tên net, không
cần vẽ dây dài, và cho ERC sạch với các chân passive.

    python -m hardware.kicad.sch_full --write
    python -m hardware.kicad.sch_full --check
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from hardware.kicad import sch_pwr, symbols
from hardware.netlist import cmp as cmp_net
from hardware.netlist import pwr as pwr_net

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "hardware" / "kicad"
PROJECT = "flytex-camera"
VERSION = "20250610"


def uid(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"flytex-full:{key}"))


@dataclass(frozen=True)
class Geometry:
    rel_x: float
    rel_y: float
    side: str  # left/right/top/bottom


def generic_symbol(name: str, pins: tuple) -> tuple[str, dict[str, Geometry]]:
    """Tạo symbol chữ nhật; pin chia trái/phải, pitch 5.08 cho dễ đọc."""
    left = [pin for index, pin in enumerate(pins) if index % 2 == 0]
    right = [pin for index, pin in enumerate(pins) if index % 2 == 1]
    rows = max(len(left), len(right), 1)
    height = max(15.24, (rows + 1) * 5.08)
    half = height / 2.0
    width = 15.24
    geom: dict[str, Geometry] = {}
    body = [
        f'\t(symbol "flytex-gen:{name}"',
        "\t\t(pin_names\n\t\t\t(offset 0.508)\n\t\t)",
        "\t\t(exclude_from_sim no)",
        "\t\t(in_bom yes)",
        "\t\t(on_board yes)",
        f'\t\t(property "Reference" "U"\n\t\t\t(at 0 {half + 2.54:.2f} 0)'
        + symbols._effects(justify="left")
        + "\t\t)",
        f'\t\t(property "Value" "{name}"\n\t\t\t(at 0 {-half - 1.27:.2f} 0)'
        + symbols._effects()
        + "\t\t)",
        f'\t\t(symbol "{name}_0_1"',
        f"\t\t\t(rectangle\n\t\t\t\t(start {-width:.2f} {half:.2f})\n"
        f"\t\t\t\t(end {width:.2f} {-half:.2f})\n"
        "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)"
        "\n\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)",
        "\t\t)",
        f'\t\t(symbol "{name}_1_1"',
    ]
    for side, items in (("left", left), ("right", right)):
        for index, pin in enumerate(items):
            y = half - (index + 1) * 5.08
            x = -width - 5.08 if side == "left" else width + 5.08
            angle = 0 if side == "left" else 180
            sp = symbols.Pin(str(pin.num), pin.name, "passive", side)
            body.append(symbols._pin(sp, x, y, angle))
            geom[str(pin.num)] = Geometry(x, -y, side)
    body += ["\t\t)", "\t)"]
    return "\n".join(body), geom


def actual_symbol(ref: str) -> symbols.Part | None:
    mapping = {
        "U1": "TPS61088",
        "U2": "TPS62840",
        "U3": "BQ25070",
        "Q1": "TPS22918",
        "Q2": "TPS22918",
    }
    if ref not in mapping:
        return None
    return next(part for part in symbols.PARTS if part.name == mapping[ref])


def build(components, title: str) -> str:
    # Bố trí lưới 5 cột; IC thực có kích thước lớn hơn nên giãn hàng.
    columns = 5
    x_step = 180.0
    y_step = 95.0
    out = [
        "(kicad_sch",
        f"\t(version {VERSION})",
        '\t(generator "flytex-sch-full")',
        '\t(generator_version "10.0")',
        f'\t(uuid "{uid("sheet:" + title)}")',
        '\t(paper "A0")',
        "\t(title_block",
        f'\t\t(title "{title}")',
        '\t\t(rev "A")',
        '\t\t(company "Flytex")',
        "\t)",
        "\t(lib_symbols",
    ]
    placements: dict[str, tuple[float, float]] = {}
    geoms: dict[str, dict[str, Geometry]] = {}
    symbols_text: list[str] = []
    for index, component in enumerate(components):
        part = actual_symbol(component.ref) if component.value in {
            "TPS61088", "TPS62840", "BQ25070", "TPS22918"
        } else None
        if part is not None:
            text = symbols.render_part(part).replace(
                f'(symbol "{part.name}"', f'(symbol "flytex-power:{part.name}"', 1
            )
            geoms[component.ref] = {
                pin.number: Geometry(
                    -12.7 if pin.side == "left" else 12.7,
                    (sch_pwr.half_height(part) - (sum(1 for p in part.pins if p.side == pin.side and p is not pin) + 1) * 2.54)
                    * (-1 if pin.side == "left" else -1),
                    pin.side,
                )
                for pin in part.pins
            }
            # Dùng đúng công thức pin_xy để label khớp.
            for pin in part.pins:
                px, py = sch_pwr.pin_xy(part, (0.0, 0.0), pin)
                geoms[component.ref][pin.number] = Geometry(px, py, pin.side)
        else:
            text, geom = generic_symbol(f"PART_{component.ref}", component.pins)
            geoms[component.ref] = geom
        symbols_text.append(text)
        col = index % columns
        row = index // columns
        placements[component.ref] = (70.0 + col * x_step, 70.0 + row * y_step)
    out += symbols_text
    out.append(sch_pwr.PWR_FLAG)
    out.append("\t)")
    flag_points: dict[str, tuple[float, float]] = {}
    power_out_nets: set[str] = set()
    for component in components:
        x, y = placements[component.ref]
        part = actual_symbol(component.ref) if component.value in {
            "TPS61088", "TPS62840", "BQ25070", "TPS22918"
        } else None
        if part is not None:
            lib = f"flytex-power:{part.name}"
            value = part.value
            footprint = part.footprint
            pin_numbers = [pin.number for pin in part.pins]
        else:
            lib = f"flytex-gen:PART_{component.ref}"
            value = component.value
            footprint = component.footprint
            pin_numbers = [pin.num for pin in component.pins]
        out += [
            "\t(symbol",
            f'\t\t(lib_id "{lib}")',
            f"\t\t(at {x:.2f} {y:.2f} 0)",
            "\t\t(unit 1)",
            "\t\t(exclude_from_sim no)",
            "\t\t(in_bom yes)",
            "\t\t(on_board yes)",
            "\t\t(dnp no)",
            f'\t\t(uuid "{uid(f"sym:{component.ref}")}")',
            f'\t\t(property "Reference" "{component.ref}"',
            f"\t\t\t(at {x:.2f} {y - 20:.2f} 0)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            f'\t\t(property "Value" "{value}"',
            f"\t\t\t(at {x:.2f} {y + 20:.2f} 0)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            f'\t\t(property "Footprint" "{footprint}"',
            f"\t\t\t(at {x:.2f} {y:.2f} 0)",
            "\t\t\t(hide yes)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            '\t\t(property "Datasheet" ""',
            f"\t\t\t(at {x:.2f} {y:.2f} 0)",
            "\t\t\t(hide yes)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
        ]
        for number in pin_numbers:
            out.append(f'\t\t(pin "{number}"\n\t\t\t(uuid "{uid(f"pin:{component.ref}:{number}")}")\n\t\t)')
        out += [
            "\t\t(instances",
            f'\t\t\t(project "{PROJECT}"',
            f'\t\t\t\t(path "/{uid("sheet:" + title)}"',
            f'\t\t\t\t\t(reference "{component.ref}")',
            "\t\t\t\t\t(unit 1)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t)",
            "\t)",
        ]
        for pin in component.pins:
            geom = geoms[component.ref][str(pin.num)]
            px = x + geom.rel_x
            py = y + geom.rel_y
            if pin.net:
                out.append(sch_pwr.label(pin.net, px, py, 180 if geom.side == "left" else 0))
                kind = next((p.kind for p in (part.pins if part else ()) if p.number == pin.num), "passive")
                if kind == "power_out":
                    power_out_nets.add(pin.net)
                if geom.side == "left" and kind in ("input", "power_in") and pin.net not in flag_points:
                    flag_points[pin.net] = (px, py)
            else:
                out.append(f'\t(no_connect (at {px:.2f} {py:.2f}) (uuid "{uid(f"nc:{component.ref}:{pin.num}")}"))')
    flag_points = {net: point for net, point in flag_points.items() if net not in power_out_nets}
    for index, (net, (fx, fy)) in enumerate(sorted(flag_points.items()), start=1):
        out += [
            "\t(symbol",
            '\t\t(lib_id "power:PWR_FLAG")',
            f"\t\t(at {fx:.2f} {fy:.2f} 0)",
            "\t\t(unit 1)",
            "\t\t(exclude_from_sim no)",
            "\t\t(in_bom no)",
            "\t\t(on_board yes)",
            "\t\t(dnp no)",
            f'\t\t(uuid "{uid(f"flag:{net}")}")',
            f'\t\t(property "Reference" "#FLG{index}"',
            f"\t\t\t(at {fx:.2f} {fy:.2f} 0)",
            "\t\t\t(hide yes)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            '\t\t(property "Value" "PWR_FLAG"',
            f"\t\t\t(at {fx:.2f} {fy:.2f} 0)",
            "\t\t\t(hide yes)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            f'\t\t(pin "1"\n\t\t\t(uuid "{uid(f"flagpin:{net}")}")\n\t\t)',
            "\t\t(instances",
            f'\t\t\t(project "{PROJECT}"',
            f'\t\t\t\t(path "/{uid("sheet:" + title)}"',
            f'\t\t\t\t\t(reference "#FLG{index}")',
            "\t\t\t\t\t(unit 1)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t)",
            "\t)",
        ]
    out += [
        f'\t(text "Full sheet: {title}. Moi chan co global label theo netlist; linh kien passive dung symbol chung."',
        "\t\t(exclude_from_sim no)",
        "\t\t(at 20 380 0)",
        '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 2 2)\n\t\t\t)\n\t\t\t(justify left)\n\t\t)',
        f'\t\t(uuid "{uid("text:" + title)}")',
        "\t)",
        "\t(sheet_instances",
        '\t\t(path "/" (page "1"))',
        "\t)",
        ")",
    ]
    return "\n".join(out) + "\n"


def outputs() -> dict[str, str]:
    return {
        "flytex-pwr-full.kicad_sch": build(pwr_net.COMPONENTS, "PWR full"),
        "flytex-cmp-full.kicad_sch": build(cmp_net.COMPONENTS, "CMP full"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = outputs()
    if args.check:
        for name, text in result.items():
            path = OUT_DIR / name
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"{name} lech nguon; chay --write", file=sys.stderr)
                return 1
        print("OK: schematic full khop nguon")
        return 0
    if args.write:
        for name, text in result.items():
            (OUT_DIR / name).write_text(text, encoding="utf-8", newline="\n")
            print(f"ghi {name}")
        return 0
    print("\n".join(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
