"""Sinh schematic KiCad PWR từ netlist: IC + global label theo tên net.

Đây là sheet pin-level đầu tiên: mỗi chân IC được gắn global label đúng tên net
trong netlist PWR. Các linh kiện thụ động sẽ được thêm ở sheet sau; netlist
`pwr-netlist.md` vẫn là nguồn sự thật cho giá trị.

    python -m hardware.kicad.sch_pwr --write
    python -m hardware.kicad.sch_pwr --check
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from hardware.kicad import symbols
from hardware.netlist import pwr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hardware" / "kicad" / "flytex-pwr.kicad_sch"
PROJECT = "flytex-camera"

PAPER = "A3"
PWR_FLAG = """	(symbol "power:PWR_FLAG"
		(power)
		(pin_numbers
			(hide yes)
		)
		(pin_names
			(offset 0)
			(hide yes)
		)
		(exclude_from_sim no)
		(in_bom no)
		(on_board yes)
		(property "Reference" "#FLG"
			(at 0 1.905 0)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Value" "PWR_FLAG"
			(at 0 3.81 0)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(symbol "PWR_FLAG_0_0"
			(pin power_out line
				(at 0 0 90)
				(length 0)
				(name "~"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
				(number "1"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
			)
		)
	)"""
POS = {
    "U1": (80.0, 70.0),
    "U2": (190.0, 70.0),
    "U3": (300.0, 70.0),
    "Q1": (80.0, 190.0),
    "Q2": (190.0, 190.0),
}


def uid(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"flytex:{key}"))


def half_height(part: symbols.Part) -> float:
    rows = max(
        sum(1 for pin in part.pins if pin.side == "left"),
        sum(1 for pin in part.pins if pin.side == "right"),
    )
    return max(10.16, (rows + 1) * 2.54) / 2.0


def pin_xy(part: symbols.Part, origin: tuple[float, float], pin: symbols.Pin) -> tuple[float, float]:
    same_side = [item for item in part.pins if item.side == pin.side]
    index = same_side.index(pin)
    y = half_height(part) - (index + 1) * 2.54
    x = -12.7 if pin.side == "left" else 12.7
    # KiCad: truc y cua symbol huong len, truc y schematic huong xuong.
    return origin[0] + x, origin[1] - y


def label(name: str, x: float, y: float, angle: int) -> str:
    justify = "right" if angle == 180 else "left"
    return (
        f'\t(global_label "{name}"\n'
        "\t\t(shape input)\n"
        f"\t\t(at {x:.2f} {y:.2f} {angle})\n"
        "\t\t(fields_autoplaced yes)\n"
        "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
        f"\t\t\t(justify {justify})\n\t\t)\n"
        f'\t\t(uuid "{uid(f"label:{name}:{x:.2f}:{y:.2f}")}")\n'
        "\t)"
    )


def render() -> str:
    out = [
        "(kicad_sch",
        "\t(version 20250610)",
        '\t(generator "flytex-sch-pwr")',
        '\t(generator_version "10.0")',
        f'\t(uuid "{uid("sheet:pwr")}")',
        f'\t(paper "{PAPER}")',
        "\t(title_block",
        '\t\t(title "Flytex Camera - PWR pin-level")',
        '\t\t(rev "A")',
        '\t\t(company "Flytex")',
        "\t)",
        "\t(lib_symbols",
    ]
    for part in symbols.PARTS:
        text = symbols.render_part(part).replace(
            f'(symbol "{part.name}"', f'(symbol "flytex-power:{part.name}"', 1
        )
        out.append(text)
    out.append(PWR_FLAG)
    out.append("\t)")
    flag_points: dict[str, tuple[float, float]] = {}
    power_out_nets: set[str] = set()
    for ref, (x, y) in POS.items():
        part = next(item for item in symbols.PARTS if item.name == {
            "U1": "TPS61088", "U2": "TPS62840", "U3": "BQ25070",
            "Q1": "TPS22918", "Q2": "TPS22918",
        }[ref])
        out += [
            "\t(symbol",
            f'\t\t(lib_id "flytex-power:{part.name}")',
            f"\t\t(at {x:.2f} {y:.2f} 0)",
            "\t\t(unit 1)",
            "\t\t(exclude_from_sim no)",
            "\t\t(in_bom yes)",
            "\t\t(on_board yes)",
            "\t\t(dnp no)",
            f'\t\t(uuid "{uid(f"sym:{ref}")}")',
            f'\t\t(property "Reference" "{ref}"',
            f"\t\t\t(at {x:.2f} {y + half_height(part) + 3.81:.2f} 0)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            f'\t\t(property "Value" "{part.value}"',
            f"\t\t\t(at {x:.2f} {y - half_height(part) - 2.54:.2f} 0)",
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)',
            "\t\t)",
            f'\t\t(property "Footprint" "{part.footprint}"',
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
        for pin in part.pins:
            out.append(f'\t\t(pin "{pin.number}"\n\t\t\t(uuid "{uid(f"pin:{ref}:{pin.number}")}")\n\t\t)')
        out += [
            "\t\t(instances",
            f'\t\t\t(project "{PROJECT}"',
            f'\t\t\t\t(path "/{uid("sheet:pwr")}"',
            f'\t\t\t\t\t(reference "{ref}")',
            "\t\t\t\t\t(unit 1)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t)",
            "\t)",
        ]
        # global label at every connected pin; no_connect for empty net
        for pin in part.pins:
            target = next(
                (item for item in pwr.COMPONENTS if item.ref == ref), None
            )
            net = ""
            if target is not None:
                for target_pin in target.pins:
                    if target_pin.num == pin.number:
                        net = target_pin.net
                        break
            px, py = pin_xy(part, (x, y), pin)
            if net:
                out.append(label(net, px, py, 180 if pin.side == "left" else 0))
                if pin.kind == "power_out":
                    power_out_nets.add(net)
                if pin.kind in ("input", "power_in") and net not in flag_points:
                    flag_points[net] = (px, py)
            else:
                out.append(f'\t(no_connect (at {px:.2f} {py:.2f}) (uuid "{uid(f"nc:{ref}:{pin.number}")}"))')
    flag_points = {
        net: point for net, point in flag_points.items() if net not in power_out_nets
    }
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
            '\t\t(pin "1"\n\t\t\t(uuid "' + uid(f"flagpin:{net}") + '")\n\t\t)',
            "\t\t(instances",
            f'\t\t\t(project "{PROJECT}"',
            f'\t\t\t\t(path "/{uid("sheet:pwr")}"',
            f'\t\t\t\t\t(reference "#FLG{index}")',
            "\t\t\t\t\t(unit 1)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t)",
            "\t)",
        ]
    out += [
        '\t(text "Sheet PWR pin-level: IC + global label theo net. Linh kien thu dong theo pwr-netlist.md."',
        '\t\t(exclude_from_sim no)',
        '\t\t(at 20 250 0)',
        '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 2 2)\n\t\t\t)\n\t\t\t(justify left)\n\t\t)',
        '\t\t(uuid "{}")'.format(uid("text:note")),
        "\t)",
        "\t(sheet_instances",
        '\t\t(path "/" (page "1"))',
        "\t)",
        ")",
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if current != text:
            print("schematic lech nguon; chay --write", file=sys.stderr)
            return 1
        print("OK: schematic PWR khop nguon")
        return 0
    if args.write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"ghi {OUT.relative_to(ROOT)}")
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
