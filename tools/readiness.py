"""Danh sách kiểm tra "sẵn sàng dựng prototype" (docs/17).

    python tools/readiness.py            # kiểm tra file/tham chiếu
    python tools/readiness.py --full     # chạy thêm các bộ sinh/kiểm tra nhanh
    python tools/readiness.py --json

Trả 0 khi tất cả đạt, 1 khi có mục hỏng. Đây là lớp kiểm tra *artifact*, không
thay `run_tests.py`: nó bắt trường hợp tài liệu/figure bị xoá hoặc tuyên bố
không còn đúng.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Item:
    code: str
    title: str
    ok: bool
    detail: str


def exists(path: str, minimum: int = 1) -> tuple[bool, str]:
    target = ROOT / path
    if not target.exists():
        return False, f"thieu {path}"
    size = target.stat().st_size if target.is_file() else sum(
        1 for item in target.rglob("*") if item.is_file()
    )
    return size >= minimum, f"{path}: {size}"


def contains(path: str, needle: str) -> tuple[bool, str]:
    target = ROOT / path
    if not target.exists():
        return False, f"thieu {path}"
    return needle in target.read_text(encoding="utf-8"), f"{path} chua {needle!r}"


def _run(argv: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, *argv], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    output = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    tail = output[-1] if output else ""
    return proc.returncode == 0, f"{' '.join(argv)} -> {proc.returncode}: {tail}"


def artifact_checks() -> list[Item]:
    checks = [
        Item("C-01", "Spec sinh mã là nguồn sự thật", *exists("spec/generated/regmap.md")),
        Item("C-02", "Regmap hiện thực hai phía", *exists("firmware/mcu/src/regmap.c")),
        Item("C-03", "Máy trạng thái nguồn + mô phỏng", *exists("sim/scenario.py")),
        Item("C-04", "MPEG-TS muxer + recorder", *exists("app/flytex/tsmux.py")),
        Item("C-05", "Hàng đợi uplink bền", *exists("app/flytex/uplink.py")),
        Item("C-06", "Tải clip lên cloud", *exists("app/flytex/upload.py")),
        Item("C-07", "OTA có xác minh + quay lui", *exists("app/flytex/ota.py")),
        Item("C-08", "Đánh thức SMS/RI", *exists("firmware/mcu/hal/stm32l0/port_stm32l0.c")),
        Item("C-09", "Đo năng lượng + nhập PPK2", *exists("tools/measure/ppk2.py")),
        Item("C-10", "Gói thiết kế PWR/CMP", *exists("hardware/pwr-design.md")),
        Item("C-10b", "Bản vẽ hình học board", *exists("hardware/boards.md")),
        Item("C-10c", "BOM thiết kế Rev A/B", *exists("hardware/bom/pwr-rev-a.csv")),
        Item("C-11", "Quy trình bring-up", *exists("hardware/bringup.md", minimum=2000)),
        Item("C-12", "Định nghĩa sẵn sàng + biên bản", *exists("docs/17-san-sang-prototype.md")),
        Item("D-18", "Pack 15 Ah đã chốt", *contains("docs/11-nhat-ky-quyet-dinh.md", "| D-18 |")),
        Item("D-19", "eMMC đã chốt", *contains("docs/11-nhat-ky-quyet-dinh.md", "| D-19 |")),
        Item("D-21", "Đổi chân lấy MODEM_RI đã chốt", *contains("docs/11-nhat-ky-quyet-dinh.md", "| D-21 |")),
        Item("M-41", "Phép đo trên thiết bị thật có trong kế hoạch", *contains("docs/08-kiem-chung.md", "M-41")),
        Item("R-31", "Rủi ro MCU reset cắt rail", *contains("docs/10-rui-ro.md", "R-31")),
        Item("R-32", "Rủi ro IWDG trong STOP", *contains("docs/10-rui-ro.md", "R-32")),
    ]
    return checks


def command_checks() -> list[Item]:
    results = [
        ("C-01c", "spec generate --check", ["spec/generate.py", "--check"]),
        ("C-09c", "tools docs_check", ["tools/docs_check/check.py"]),
        ("C-10c", "hardware calc check", ["-m", "hardware.calc.cli", "--check"]),
        ("C-10d", "hardware geom check", ["-m", "hardware.geom.cli", "--check"]),
    ]
    items = []
    for code, title, argv in results:
        ok, detail = _run(argv)
        items.append(Item(code, title, ok, detail))
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="chạy thêm command checks")
    parser.add_argument("--json", action="store_true", help="in JSON")
    args = parser.parse_args(argv)

    items = artifact_checks()
    if args.full:
        items += command_checks()
    failed = [item for item in items if not item.ok]
    if args.json:
        print(json.dumps(
            [{"code": item.code, "title": item.title, "ok": item.ok,
              "detail": item.detail} for item in items],
            ensure_ascii=True, indent=1,
        ))
    else:
        for item in items:
            print(f"{'PASS' if item.ok else 'FAIL'} {item.code} {item.title}: {item.detail}")
        print(f"TONG: {len(items) - len(failed)}/{len(items)} dat")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
