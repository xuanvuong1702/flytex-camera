"""Sinh schematic khối PWR/CMP từ spec/schematic.toml.

Đây là schematic **mức khối** (block-level): mỗi khối là một chức năng, các net
được nối bằng nhãn tên. Không có số chân linh kiện thật; pin-level chỉ vẽ được
sau khi chốt VSET buck, RI modem, pinout camera và pack/BMS.

    python -m hardware.schematic.render            # in tóm tắt
    python -m hardware.schematic.render --write    # ghi SVG
    python -m hardware.schematic.render --check    # CI
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "spec" / "schematic.toml"
OUT_DIR = ROOT / "hardware" / "schematic"
SCALE = 4.0  # px/mm

POWER_NETS = {"GND", "VBAT", "VBUS", "+3V3", "+5V_BOOST", "+5V_SOC", "+5V_MODEM"}


def load(path: Path | None = None) -> dict:
    with (path or SPEC_PATH).open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("schema") != "flytex.blocksch/1":
        raise ValueError("schema schematic.toml khong dung")
    return data


def pins(sheet: dict):
    for block in sheet["blocks"]:
        for pin in block["pins"]:
            yield block, pin


def validate(data: dict) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    page = data["page"]
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    for sheet in data["sheets"]:
        for block in sheet["blocks"]:
            key = f"{sheet['id']}:{block['id']}"
            if key in ids:
                issues.append(("error", f"trung block id {key}"))
            ids.add(key)
            if not (0 < block["x"] < page["width_mm"] and 0 < block["y"] < page["height_mm"]):
                issues.append(("error", f"{block['id']} ngoai trang"))
            if block["x"] + block["w"] > page["width_mm"]:
                issues.append(("error", f"{block['id']} tran ngang"))
            if block["y"] + block["h"] > page["height_mm"]:
                issues.append(("error", f"{block['id']} tran doc"))
            names = [pin["name"] for pin in block["pins"]]
            if len(names) != len(set(names)):
                issues.append(("error", f"{block['id']} trung ten pin"))
            for pin in block["pins"]:
                net = pin["net"].strip()
                if not net:
                    continue
                if net.startswith("TBD_"):
                    issues.append(("warn", f"{block['id']}.{pin['name']} chua chot {net}"))
                    continue
                counts[net] += 1
    for net, count in sorted(counts.items()):
        if count < 2:
            issues.append(("error", f"net {net} chi co {count} dau"))
    for sheet in data["sheets"]:
        if not any(block["id"] == "B2B" for block in sheet["blocks"]):
            issues.append(("error", f"sheet {sheet['id']} thieu J_B2B"))
    return issues


def net_colour(net: str) -> str:
    if net == "GND":
        return "#222222"
    if net.startswith("+") or net in {"VBAT", "VBUS"}:
        return "#b02020"
    if net.startswith(("USB", "SVC")):
        return "#1f7a1f"
    if net.startswith(("MIPI", "CAM")):
        return "#6a1b9a"
    if net.startswith("TBD"):
        return "#888888"
    return "#1a3d7c"


def _pin_text(pin: dict) -> str:
    net = pin["net"].strip()
    return f"{pin['name']} = {net}" if net else f"{pin['name']} (NC)"


def render_sheet(sheet: dict, page: dict) -> str:
    width = page["width_mm"] * SCALE
    height = page["height_mm"] * SCALE
    out = [
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'),
        '<rect width="100%" height="100%" fill="#fbfbf8"/>',
        (f'<text x="20" y="28" font-family="sans-serif" font-size="18" '
        f'font-weight="bold">{escape(sheet["title"])}</text>'),
        (f'<text x="20" y="46" font-family="sans-serif" font-size="10">'
        f'{escape(sheet.get("rev", ""))} — block-level, không phải pin-level. '
        f'Nhãn net thay cho dây; xem hardware/schematic/README.md</text>'),
    ]
    for block in sheet["blocks"]:
        x = block["x"] * SCALE
        y = block["y"] * SCALE
        w = block["w"] * SCALE
        h = block["h"] * SCALE
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="6" fill="#eef3fa" stroke="#26466f" stroke-width="1.5"/>'
        )
        out.append(
            f'<text x="{x + 8:.1f}" y="{y + 16:.1f}" font-family="sans-serif" '
            f'font-size="12" font-weight="bold" fill="#123">'
            f'{escape(block["id"])} · {escape(block["name"])}</text>'
        )
        left = (len(block["pins"]) + 1) // 2
        for index, pin in enumerate(block["pins"]):
            on_left = index < left
            column = index if on_left else index - left
            total = left if on_left else len(block["pins"]) - left
            span = h - 34.0
            py = y + 30.0 + (span * (column + 0.5) / max(1, total))
            if on_left:
                sx, ex = x, x + 10.0
                anchor = "start"
            else:
                sx, ex = x + w, x + w - 10.0
                anchor = "end"
            net = pin["net"].strip()
            colour = net_colour(net)
            out.append(
                f'<line x1="{sx:.1f}" y1="{py:.1f}" x2="{ex:.1f}" y2="{py:.1f}" '
                f'stroke="{colour}" stroke-width="1"/>'
            )
            out.append(
                f'<circle cx="{sx:.1f}" cy="{py:.1f}" r="2" fill="{colour}"/>'
            )
            out.append(
                f'<text x="{ex + (2 if on_left else -2):.1f}" y="{py + 3:.1f}" '
                f'text-anchor="{anchor}" font-family="sans-serif" font-size="7" '
                f'fill="{colour}">{escape(_pin_text(pin))}</text>'
            )
    out.append(
        f'<text x="20" y="{height - 16:.0f}" font-family="sans-serif" font-size="8" '
        f'fill="#555">Sinh từ spec/schematic.toml — kiểm tra: '
        f'python -m hardware.schematic.render --check</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def outputs(data: dict) -> dict[Path, str]:
    return {
        OUT_DIR / f"{sheet['id']}-blocks.svg": render_sheet(sheet, data["page"])
        for sheet in data["sheets"]
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = load()
    except (OSError, ValueError, KeyError) as exc:
        print(f"LOI SPEC: {exc}", file=sys.stderr)
        return 2
    issues = validate(data)
    errors = [msg for level, msg in issues if level == "error"]
    warns = [msg for level, msg in issues if level == "warn"]
    if args.check:
        if errors:
            for message in errors:
                print(f"LOI: {message}", file=sys.stderr)
            return 1
        stale = []
        for path, content in outputs(data).items():
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != content:
                stale.append(path.relative_to(ROOT))
        if stale:
            print("SVG lech spec, chay --write:", file=sys.stderr)
            for path in stale:
                print(f"  - {path}", file=sys.stderr)
            return 1
        print(
            f"OK: schematic khoi hop le, {len(data['sheets'])} sheet, "
            f"{sum(len(s['blocks']) for s in data['sheets'])} block, {len(warns)} canh bao"
        )
        return 0
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for path, content in outputs(data).items():
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"ghi {path.relative_to(ROOT)}")
        return 0
    for message in errors:
        print(f"ERROR: {message}")
    for message in warns:
        print(f"WARN: {message}")
    print(
        f"{len(data['sheets'])} sheet, "
        f"{sum(len(s['blocks']) for s in data['sheets'])} block, "
        f"{len(errors)} loi, {len(warns)} canh bao"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
