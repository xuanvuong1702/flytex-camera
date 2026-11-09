"""Kiểm tra gói sản xuất (fab readiness) trước khi gửi xưởng.

Không thay thế DRC/DFM của kỹ sư PCB. Mục đích: chặn việc gửi một bản vẽ còn
thiếu footprint, PCB, Gerber, drill, CPL hoặc DRC.

    python tools/fab_check.py
    python tools/fab_check.py --check   # exit 1 nếu chưa đủ
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KICAD = ROOT / "hardware" / "kicad"
FAB = ROOT / "hardware" / "fab"


def schematic_footprints() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for name in ("flytex-pwr-full.kicad_sch", "flytex-cmp-full.kicad_sch"):
        path = KICAD / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for block in re.split(r"\n\t\(symbol\n", text)[1:]:
            ref = re.search(r'\(property "Reference" "([^"]+)"', block)
            fp = re.search(r'\(property "Footprint" "([^"]*)"', block)
            if ref and fp:
                found.append((name, ref.group(1), fp.group(1)))
    return found


def audit() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    pcb = KICAD / "flytex.kicad_pcb"
    checks.append(("PCB layout", pcb.exists(), str(pcb.relative_to(ROOT))))
    gerbers = list((FAB / "gerbers").glob("*.gbr")) if (FAB / "gerbers").exists() else []
    checks.append(("Gerber", bool(gerbers), f"{len(gerbers)} file .gbr"))
    drills = list((FAB / "gerbers").glob("*.drl")) if (FAB / "gerbers").exists() else []
    checks.append(("Drill", bool(drills), f"{len(drills)} file .drl"))
    checks.append(("BOM", (ROOT / "hardware" / "bom" / "pwr-rev-a.csv").exists(), "hardware/bom"))
    checks.append(("CPL/pos", (FAB / "cpl.csv").exists(), "hardware/fab/cpl.csv"))
    checks.append(("DRC report", (FAB / "drc.rpt").exists(), "hardware/fab/drc.rpt"))
    checks.append(("Stackup", (FAB / "stackup.md").exists(), "hardware/fab/stackup.md"))
    checks.append(("Test plan", (ROOT / "docs" / "16-van-hanh.md").exists(), "docs/16"))
    bad = [
        (sheet, ref, fp)
        for sheet, ref, fp in schematic_footprints()
        if not fp or fp.startswith("flytex:") or fp.startswith("Connector_Generic:")
    ]
    checks.append(("Footprint thật", not bad, f"{len(bad)} linh kiện còn generic/placeholder: " + ", ".join(f"{sheet}:{ref}" for sheet, ref, _ in bad)))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    checks = audit()
    print("| Hạng mục | Kết quả | Chi tiết |")
    print("|---|---|---|")
    for name, ok, detail in checks:
        print(f"| {name} | {'ĐẠT' if ok else 'THIẾU'} | {detail} |")
    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print(f"\nCHƯA GỬI XƯỞNG: {len(failed)} hạng mục thiếu: {', '.join(failed)}")
        return 1 if args.check else 0
    print("\nĐỦ ĐIỀU KIỆN GỬI XƯỞNG (theo checklist này)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
