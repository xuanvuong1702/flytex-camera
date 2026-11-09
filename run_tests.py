#!/usr/bin/env python3
"""Chạy toàn bộ kiểm tra của repo, không cần phần cứng.

    python run_tests.py              # tất cả
    python run_tests.py --quick      # bỏ mô phỏng end-to-end
    python run_tests.py --only app   # chỉ các bước có tên chứa "app"
    python run_tests.py --list

Trả 0 nếu mọi bước đạt, 1 nếu có bước hỏng.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _streams_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def discover(pattern: str) -> list[Path]:
    return sorted(ROOT.glob(pattern))


def build_steps(quick: bool) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = [
        ("spec: file sinh khớp spec", [PY, "spec/generate.py", "--check"]),
        ("spec: test spec và bộ sinh", [PY, "spec/tests/test_spec.py"]),
        ("hardware: test tính toán thiết kế", [PY, "hardware/calc/tests/test_pwr.py"]),
        ("hardware: báo cáo khớp tính toán", [PY, "-m", "hardware.calc.cli", "--check"]),
        ("hardware: test hình học board", [PY, "hardware/geom/tests/test_geom.py"]),
        ("hardware: bản vẽ khớp spec", [PY, "-m", "hardware.geom.cli", "--check"]),
        ("hardware: BOM thiết kế", [PY, "hardware/bom/tests/test_bom.py"]),
        ("hardware: sổ linh kiện", [PY, "hardware/parts/tests/test_parts.py"]),
        ("hardware: sổ linh kiện khớp spec", [PY, "-m", "hardware.parts.check", "--check"]),
        ("firmware: build và unit test", [PY, "firmware/mcu/tests/build.py", "test"]),
        ("firmware: include C di động", [PY, "tools/check_c_includes.py"]),
        ("firmware: thư viện mô phỏng", [PY, "firmware/mcu/tests/build.py", "lib"]),
    ]
    for path in discover("app/tests/test_*.py"):
        steps.append((f"app: {path.name}", [PY, str(path.relative_to(ROOT))]))
    for path in discover("tools/**/test_*.py"):
        steps.append((f"tools: {path.relative_to(ROOT).as_posix()}", [PY, str(path.relative_to(ROOT))]))
    steps.append(("tools: kiểm tra tài liệu", [PY, "tools/docs_check/check.py"]))
    steps.append(("readiness: checklist sẵn sàng", [PY, "tools/readiness.py", "--full"]))
    steps.append(("app: cli selftest", [PY, "-m", "flytex.cli", "selftest"]))
    steps.append(("app: cli sim 20s", [PY, "-m", "flytex.cli", "sim", "--seconds", "20"]))
    if not quick:
        steps.append(("sim: end-to-end", [PY, "sim/run.py", "--scenario", "all", "--quiet"]))
    return steps


REQUIRED = {
    "spec/tests/test_spec.py": 1,
    "hardware/calc/tests/test_pwr.py": 1,
    "hardware/pwr-design.md": 1,
    "hardware/geom/tests/test_geom.py": 1,
    "hardware/boards.md": 1,
    "hardware/bom/pwr-rev-a.csv": 1,
    "hardware/parts-register.md": 1,
    "firmware/mcu/tests/build.py": 1,
    "app/tests/test_*.py": 1,
    "tools/**/test_*.py": 1,
    "tools/docs_check/check.py": 1,
    "tools/check_c_includes.py": 1,
    "tools/readiness.py": 1,
    "sim/run.py": 1,
}


def missing_required() -> list[str]:
    """Không cho phép 'xanh giả' khi một khu vực chưa có test."""
    missing: list[str] = []
    for pattern, minimum in REQUIRED.items():
        if len(discover(pattern)) < minimum:
            missing.append(pattern)
    return missing


def main(argv: list[str] | None = None) -> int:
    _streams_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="bỏ mô phỏng end-to-end")
    parser.add_argument("--only", help="chỉ chạy bước có tên chứa chuỗi này")
    parser.add_argument("--list", action="store_true", help="liệt kê bước rồi thoát")
    args = parser.parse_args(argv)

    steps = build_steps(args.quick)
    if args.only:
        steps = [step for step in steps if args.only.lower() in step[0].lower()]
    if args.list:
        for name, argv_ in steps:
            print(f"{name}: {' '.join(argv_)}")
        return 0
    if not steps:
        print(f"khong co buoc nao khop --only {args.only!r}", file=sys.stderr)
        return 2

    missing = [] if args.only else missing_required()
    if missing:
        print("THIEU THANH PHAN BAT BUOC (khong chay de tranh 'xanh gia'):", file=sys.stderr)
        for pattern in missing:
            print(f"  - {pattern}", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "app"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    failures: list[tuple[str, int, float]] = []
    total_start = time.monotonic()
    width = max(len(name) for name, _ in steps)
    for index, (name, argv_) in enumerate(steps, start=1):
        print(f"[{index:>2}/{len(steps)}] {name.ljust(width)} ... ", end="", flush=True)
        start = time.monotonic()
        try:
            proc = subprocess.run(argv_, cwd=ROOT, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=1800)
            code = proc.returncode
            output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            code = 124
            output = "qua thoi gian cho (1800 s)"
        except FileNotFoundError as exc:
            code = 127
            output = f"khong chay duoc: {exc}"
        elapsed = time.monotonic() - start
        if code == 0:
            print(f"OK ({elapsed:.1f}s)")
        else:
            print(f"FAIL ma {code} ({elapsed:.1f}s)")
            failures.append((name, code, elapsed))
            tail = "\n".join(output.strip().splitlines()[-40:])
            if tail:
                print("    " + tail.replace("\n", "\n    "))

    elapsed_total = time.monotonic() - total_start
    print()
    if failures:
        print(f"THAT BAI: {len(failures)}/{len(steps)} buoc, {elapsed_total:.1f}s")
        for name, code, _ in failures:
            print(f"  - {name} (ma {code})")
        return 1
    print(f"DAT: {len(steps)}/{len(steps)} buoc, {elapsed_total:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
