#!/usr/bin/env python3
"""Chạy mô phỏng end-to-end: firmware C thật + ứng dụng Linux thật.

    python sim/run.py --list
    python sim/run.py --scenario basic
    python sim/run.py --scenario all

Cần thư viện firmware: python firmware/mcu/tests/build.py lib
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "app"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="basic", help="tên kịch bản hoặc 'all'")
    parser.add_argument("--list", action="store_true", help="liệt kê kịch bản")
    parser.add_argument("--quiet", action="store_true", help="chỉ in kết quả cuối")
    args = parser.parse_args(argv)

    from sim.ffi import FirmwareMissing
    from sim.scenario import SCENARIOS, all_scenarios, run

    if args.list:
        for name in all_scenarios():
            print(name)
        return 0

    names = all_scenarios() if args.scenario == "all" else [args.scenario]
    unknown = [name for name in names if name not in SCENARIOS]
    if unknown:
        print(f"không có kịch bản: {', '.join(unknown)}", file=sys.stderr)
        return 2

    failures = 0
    for name in names:
        if not args.quiet:
            print(f"=== {name} ===")
        try:
            passed, detail = run(name)
        except FirmwareMissing as exc:
            print(f"THIẾU FIRMWARE: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001 - lỗi hạ tầng mô phỏng
            print(f"LỖI HẠ TẦNG ở {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            traceback.print_exc(limit=5)
            return 2
        if passed:
            print(f"OK {name}: {detail}")
        else:
            failures += 1
            print(f"FAIL {name}: {detail}")
        if not args.quiet:
            print()
    if failures:
        print(f"THẤT BẠI: {failures}/{len(names)} kịch bản")
        return 1
    print(f"ĐẠT: {len(names)} kịch bản")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
