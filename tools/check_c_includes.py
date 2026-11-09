"""Kiểm tra tính di động C: file dùng NULL phải include <stddef.h>.

GCC trên Ubuntu báo lỗi `NULL undeclared` khi thiếu include, trong khi một số
bản clang trên Windows vẫn biên dịch được nhờ include gián tiếp. CI dùng gcc,
nên thêm lớp kiểm tra này để lỗi không quay lại.

    python tools/check_c_includes.py [--root .]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NULL_RE = re.compile(r"\bNULL\b")
INCLUDE_RE = re.compile(r"^\s*#\s*include\s*<\s*stddef\.h\s*>", re.MULTILINE)
SKIP_DIRS = {".git", "build", "__pycache__"}


def offenders(root: Path) -> list[Path]:
    bad: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".c", ".h"}:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if "firmware" not in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if NULL_RE.search(text) and not INCLUDE_RE.search(text):
            bad.append(path)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="thu muc goc repo")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    bad = offenders(root)
    if bad:
        print("LOI: file dung NULL nhung thieu #include <stddef.h>:", file=sys.stderr)
        for path in bad:
            print(f"  - {path.relative_to(root)}", file=sys.stderr)
        return 1
    print("OK: moi file C dung NULL deu co <stddef.h>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
