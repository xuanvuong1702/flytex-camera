"""Test tính năng devkit: môi trường, sim, camera, modem, mạng.

    python3 devkit/scripts/feature_test.py --dry-run
    python3 devkit/scripts/feature_test.py --camera
    python3 devkit/scripts/feature_test.py --modem /dev/ttyUSB0
    python3 devkit/scripts/feature_test.py --network 8.8.8.8
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], timeout: float = 15.0) -> tuple[int, str]:
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "app") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False, env=env
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()[-600:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def sim() -> tuple[bool, str]:
    code, out = run([sys.executable, "-m", "flytex.cli", "sim", "--seconds", "5"], 60)
    return code == 0, out


def camera() -> tuple[bool, str]:
    nodes = sorted(glob.glob("/dev/video*"))
    if not nodes:
        return False, "khong thay /dev/video*; kiem FPC va driver"
    if not shutil.which("v4l2-ctl"):
        return True, f"co {nodes}; thieu v4l2-ctl de kiem format"
    code, out = run(["v4l2-ctl", "--list-devices"])
    return code == 0, out or ", ".join(nodes)


def modem(device: str) -> tuple[bool, str]:
    if not Path(device).exists():
        return False, f"khong thay {device}"
    try:
        fd = os.open(device, os.O_RDWR | os.O_NOCTTY)
    except OSError as exc:
        return False, f"mo {device} loi: {exc}"
    try:
        os.write(fd, b"AT\r\n")
        time.sleep(0.3)
        data = os.read(fd, 256)
        return b"OK" in data, data.decode("latin-1", "replace")
    except OSError as exc:
        return False, f"AT loi: {exc}"
    finally:
        os.close(fd)


def network(host: str) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, 53), timeout=3.0):
            return True, f"TCP {host}:53 OK"
    except OSError as exc:
        return False, str(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--camera", action="store_true")
    parser.add_argument("--modem", nargs="?", const="/dev/ttyUSB0")
    parser.add_argument("--network", nargs="?", const="8.8.8.8")
    parser.add_argument("--sim", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print("DRY-RUN: se kiem tra")
        print("- Python:", sys.version.split()[0], platform.system())
        print("- file app:", (ROOT / "app/flytex/cli.py").exists())
        print("- sim:", [sys.executable, "-m", "flytex.cli", "sim", "--seconds", "5"])
        print("- camera: /dev/video* + v4l2-ctl")
        print("- modem: AT tren /dev/ttyUSB*")
        print("- network: TCP 8.8.8.8:53")
        return 0
    results: list[tuple[str, bool, str]] = []
    if args.sim or not any((args.camera, args.modem, args.network)):
        results.append(("sim", *sim()))
    if args.camera:
        results.append(("camera", *camera()))
    if args.modem:
        results.append(("modem", *modem(args.modem)))
    if args.network:
        results.append(("network", *network(args.network)))
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
