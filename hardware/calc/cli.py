"""CLI cho gói tính toán phần cứng.

    python -m hardware.calc.cli            # in báo cáo
    python -m hardware.calc.cli --write    # ghi hardware/pwr-design.md
    python -m hardware.calc.cli --check    # CI: file phải khớp tính toán
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # chạy trực tiếp: python hardware/calc/cli.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hardware.calc import design, report  # type: ignore import-not-found
else:
    from . import design, report

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "hardware" / "pwr-design.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="ghi file báo cáo")
    parser.add_argument("--check", action="store_true", help="kiểm tra file khớp tính toán")
    args = parser.parse_args(argv)

    text = report.render()
    failed = [check for check in design.checks() if not check.passed]
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
        if current != text:
            print("hardware/pwr-design.md lech tinh toan; chay --write", file=sys.stderr)
            return 1
        if failed:
            print(f"{len(failed)} kiem tra khong dat:", file=sys.stderr)
            for check in failed:
                print(f"  - {check.name}: {check.value} (can {check.limit})", file=sys.stderr)
            return 1
        print("OK: pwr-design.md khop tinh toan, moi kiem tra dat")
        return 0
    if args.write:
        TARGET.write_text(text, encoding="utf-8", newline="\n")
        print(f"ghi {TARGET.relative_to(ROOT)}")
        return 0
    sys.stdout.write(text)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
