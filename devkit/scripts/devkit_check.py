"""Kiểm tra devkit trước khi mua và sau khi cắm.

    python3 devkit/scripts/devkit_check.py --dry-run   # chỉ kiểm tài liệu/software
    python3 devkit/scripts/devkit_check.py             # kiểm thêm phần cứng đang có
"""

from __future__ import annotations

import argparse
import glob
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check_files() -> list[tuple[str, bool, str]]:
    required = [
        "devkit/README.md",
        "devkit/bom.csv",
        "devkit/wiring.md",
        "devkit/flash.md",
        "devkit/config/devkit.json",
        "devkit/systemd/flytex-device.service",
        "devkit/scripts/feature_test.py",
        "docs/21-ke-hoach-2-muc-tieu.md",
        "app/flytex/cli.py",
    ]
    return [(f"file {name}", (ROOT / name).exists(), name) for name in required]


def check_tools() -> list[tuple[str, bool, str]]:
    tools = ["python3", "ffmpeg", "ping", "systemctl", "v4l2-ctl"]
    return [
        (f"tool {name}", shutil.which(name) is not None, shutil.which(name) or "khong co")
        for name in tools
    ]


def check_hardware() -> list[tuple[str, bool, str]]:
    videos = sorted(glob.glob("/dev/video*"))
    serials = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return [
        ("camera /dev/video*", bool(videos), ", ".join(videos) or "khong thay"),
        ("modem USB serial", bool(serials), ", ".join(serials) or "khong thay"),
        ("Linux", platform.system() == "Linux", platform.system()),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chi kiem file/software")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    checks = check_files()
    if not args.dry_run:
        checks += check_tools() + check_hardware()
    if args.json:
        print(json.dumps(
            [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
            ensure_ascii=False, indent=2,
        ))
    else:
        print("| Kiểm tra | Kết quả | Chi tiết |")
        print("|---|---|---|")
        for name, ok, detail in checks:
            print(f"| {name} | {'OK' if ok else 'THIẾU'} | {detail} |")
    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print(f"\nTHIẾU: {len(failed)} muc: {', '.join(failed)}")
        return 1
    print("\nOK: devkit san sang")
    return 0


if __name__ == "__main__":
    sys.exit(main())
