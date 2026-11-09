"""Kiểm tra sổ linh kiện với thiết kế và sinh báo cáo.

    python -m hardware.parts.check            # in tóm tắt + vấn đề
    python -m hardware.parts.check --write    # ghi hardware/parts-register.md
    python -m hardware.parts.check --check    # CI: file khớp + cấu trúc hợp lệ
    python -m hardware.parts.check --strict   # fail nếu còn blocker (cổng trước khi mua)
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTS_PATH = ROOT / "spec" / "parts.toml"
TARGET = ROOT / "hardware" / "parts-register.md"
BOM_FILES = (
    ROOT / "hardware" / "bom" / "pwr-rev-a.csv",
    ROOT / "hardware" / "bom" / "cmp-rev-b.csv",
)
CRITICAL_BLOCKS = {
    "boost", "buck", "charger", "mcu", "nvm", "soc_switch", "modem_switch",
    "usb_mux", "usb_c", "b2b", "pack", "modem", "camera", "sd",
}


@dataclass(frozen=True)
class Issue:
    level: str  # blocker | warn | info
    item: str
    message: str


def load_parts() -> tuple[dict[str, dict], dict[str, dict]]:
    with PARTS_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("schema") != "flytex.parts/1":
        raise ValueError("schema parts.toml khong dung")
    parts = {}
    for part in data.get("parts", []):
        pid = str(part["id"])
        if pid in parts:
            raise ValueError(f"trung id linh kien: {pid}")
        parts[pid] = part
    external = {}
    for item in data.get("external", []):
        eid = str(item["id"])
        if eid in external:
            raise ValueError(f"trung id module: {eid}")
        external[eid] = item
    return parts, external


def load_bom() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in BOM_FILES:
        with path.open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def param(part: dict, name: str):
    for item in part.get("params", []):
        if item["name"] == name:
            return item["value"]
    return None


def structural_issues(parts: dict[str, dict], external: dict[str, dict],
                      bom: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    mpns = {str(part["mpn"]) for part in parts.values()}
    mpns |= {
        str(item["mpn"]) for item in external.values() if str(item.get("mpn", "")).strip()
    }
    for row in bom:
        if row["dnp"] != "no" or row["block"] not in CRITICAL_BLOCKS:
            continue
        if row["verify"] == "not-chosen":
            continue
        if row["mpn"] not in mpns:
            issues.append(Issue(
                "blocker", row["mpn"],
                f"co trong BOM ({row['ref']}) nhung thieu trong spec/parts.toml",
            ))
    for pid, part in {**parts, **external}.items():
        verified = str(part.get("verified", "no"))
        if verified not in {"yes", "partial", "no"}:
            issues.append(Issue("blocker", pid, f"verified khong hop le: {verified}"))
        if not str(part.get("datasheet", "")).strip() and verified != "no":
            issues.append(Issue("blocker", pid, "thieu URL datasheet"))
        if verified == "no" and not str(part.get("notes", "")).strip():
            issues.append(Issue("blocker", pid, "chua xac minh ma khong ghi ly do"))
        for item in part.get("params", []):
            value = item.get("value")
            if not isinstance(value, (int, float, bool)) or isinstance(value, str):
                issues.append(Issue("blocker", pid, f"param {item['name']} khong phai so/bool"))
    return issues


def design_issues(parts: dict[str, dict], external: dict[str, dict],
                  bom: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    blocks = {row["block"] for row in bom}
    for row in bom:
        if row["verify"] == "not-chosen" and row["block"] == "buck_vset":
            issues.append(Issue(
                "blocker", "U2",
                "chua chot gia tri dien tro VSET (R_SET) cho TPS62840",
            ))
            continue
        if row["verify"] == "not-chosen" and not row["block"].startswith("charger_"):
            issues.append(Issue(
                "blocker", row["ref"],
                f"linh kien {row['block']} chua chon: {row['notes']}",
            ))

    def need(pid: str, name: str, op: str, limit: float, level: str, message: str) -> None:
        lookup = parts.get(pid) or external.get(pid) or {}
        value = param(lookup, name)
        if value is None:
            issues.append(Issue(level, pid, f"thieu thong so {name}"))
            return
        ok = {"<=": value <= limit, ">=": value >= limit,
              "<": value < limit, ">": value > limit}[op]
        if not ok:
            issues.append(Issue(level, pid, message))

    need("U1", "vin_min_v", "<=", 3.0, "blocker", "boost khong chay duoc o 3,0 V")
    need("U1", "vin_max_v", ">=", 3.65, "blocker", "boost khong chiu duoc pack day")
    need("U1", "iout_a", ">=", 3.0, "blocker", "boost thieu dong ra")
    need("U1", "ilim_a", ">=", 6.52 * 1.2, "blocker", "gioi han dong boost qua sat dinh")
    need("U1", "temp_min_c", "<=", -20, "warn", "nhiet do boost khong phu hop")
    need("U1", "temp_max_c", ">=", 60, "warn", "nhiet do boost khong phu hop")

    need("U2", "vin_min_v", "<=", 3.0, "blocker", "buck khong chay o pin yeu")
    need("U2", "vin_max_v", ">=", 3.65, "blocker", "buck khong chiu pack day")
    need("U2", "iout_a", ">=", 0.75, "blocker", "buck thieu dong")
    need("U2", "iq_ua", "<=", 5.0, "warn", "dong nghi buck qua cao")
    if "buck_vset" not in blocks:
        issues.append(Issue(
            "blocker", "U2",
            "BOM thieu dien tro VSET cho TPS62840",
        ))

    need("U3", "vin_min_v", "<=", 4.5, "blocker", "sac khong nhan duoc 5 V")
    need("U3", "vin_max_v", ">=", 5.5, "blocker", "sac khong chiu duoc 5 V")
    need("U3", "ichg_a", ">=", 0.9, "blocker", "sac khong dat 900 mA")
    need("U3", "vfloat_v", "<=", 3.6, "blocker", "float cao hon 3,6 V cho LFP")
    need("U3", "vfloat_v", ">=", 3.4, "blocker", "float qua thap, khong nap duoc")
    if param(parts.get("U3", {}), "power_path") is not True:
        issues.append(Issue("blocker", "U3", "sac khong co power-path (D-16)"))
    if param(parts.get("U3", {}), "ntc") is not True:
        issues.append(Issue("blocker", "U3", "sac khong co NTC phan cung (FR-10)"))
    need("U3", "ntc_r1_ohm", ">=", 1000.0, "warn", "thieu R1 NTC")
    need("U3", "ntc_r2_ohm", ">=", 1000.0, "warn", "thieu R2 NTC")
    if param(parts.get("U3", {}), "approved") is not True:
        issues.append(Issue("blocker", "U3", "chua chon IC sac"))

    need("U4", "stop_ua", "<=", 2.0, "blocker", "MCU nghi qua cao")
    need("U4", "gpio", ">=", 15, "warn", "co the thieu GPIO")
    need("U4", "temp_min_c", "<=", -20, "warn", "nhiet do MCU khong phu hop")
    need("U4", "temp_max_c", ">=", 60, "warn", "nhiet do MCU khong phu hop")

    need("U5", "vcc_min_v", "<=", 3.135, "blocker", "EEPROM khong chay o 3,3 V -5%")
    need("U5", "vcc_max_v", ">=", 3.465, "blocker", "EEPROM khong chiu 3,3 V +5%")

    need("Q1Q2", "vin_max_v", ">=", 5.5, "blocker", "cong tac tai khong chiu 5 V")
    need("Q1Q2", "imax_a", ">=", 1.8, "blocker", "cong tac tai thieu dong modem")

    need("U6", "channels", ">=", 2, "blocker", "mux USB thieu kenh")
    if param(parts.get("U6", {}), "usb_hs") is not True:
        issues.append(Issue("blocker", "U6", "mux khong dat USB high-speed"))

    need("J2", "pins", ">=", 26, "blocker", "J_B2B thieu chan")
    need("J3", "current_a", ">=", 8.0, "warn", "connector pack thieu du")

    need("MODEM", "vbat_min_v", "<=", 3.8, "blocker", "modem khong chay o 3,8 V")
    need("MODEM", "vbat_max_v", ">=", 3.8, "blocker", "modem khong chiu 3,8 V")
    if param(external.get("MODEM", {}), "peak_current_a") == 2.0:
        issues.append(Issue(
            "warn", "MODEM",
            "dinh dong 2 A la gia dinh chua do; xac nhan bang M-36",
        ))
    if param(external.get("MODEM", {}), "ri_pin") is not True:
        issues.append(Issue(
            "blocker", "MODEM",
            "chua xac nhan breakout dua RI ra header - kenh Watch khong chay",
        ))
    if param(external.get("SOC", {}), "pinout_ingested") is not True:
        issues.append(Issue(
            "blocker", "SOC",
            "chua nap ban ve 112 chan cua Core1106D - khong ve duoc CMP",
        ))
    if param(external.get("SOC", {}), "usb_ports") != 1:
        issues.append(Issue("warn", "SOC", "so cong USB khac gia dinh D-20"))
    if param(external.get("CAMERA", {}), "pinout_known") is not True:
        issues.append(Issue("blocker", "CAMERA", "chua chon camera va pinout FPC"))
    if param(external.get("PACK", {}), "docs_ready") is not True:
        issues.append(Issue(
            "blocker", "PACK",
            "thieu ho so UN38.3/IEC 62133 va so do tu tieu cua pack EVE/Daly",
        ))
    if param(parts.get("J1", {}), "waterproof") is not True:
        issues.append(Issue("warn", "J1", "USB-C chua phai loai chong nuoc (O-06)"))
    if param(parts.get("L1", {}), "isat_a") == 9.0:
        issues.append(Issue("warn", "L1", "Isat 9 A chua xac minh o 125 do C"))
    return issues


def render() -> str:
    parts, external = load_parts()
    bom = load_bom()
    issues = structural_issues(parts, external, bom) + design_issues(parts, external, bom)
    blockers = [i for i in issues if i.level == "blocker"]
    warns = [i for i in issues if i.level == "warn"]
    out = [
        "# Sổ linh kiện và đối chiếu thiết kế (sinh tự động)",
        "",
        "- Nguồn: `spec/parts.toml`; kiểm tra: `python -m hardware.parts.check --check`.",
        ("- `verified`: **yes** đã đối chiếu datasheet, **partial** mới một phần, "
        "**no** chưa mở datasheet."),
        (f"- Kết quả: **{len(blockers)} blocker**, {len(warns)} cảnh báo. "
        "Blocker là việc phải đóng trước khi đặt hàng."),
        "",
        "## 1. Linh kiện chính",
        "",
        "| ID | MPN | Gói | Xác minh | Datasheet | Ghi chú |",
        "|---|---|---|---|---|---|",
    ]
    for pid, part in parts.items():
        out.append(
            f"| {pid} | {part['mpn']} | {part.get('package', '')} | "
            f"{part.get('verified', 'no')} | {part.get('datasheet', '')} | "
            f"{part.get('notes', '')} |"
        )
    out += ["", "### Thông số then chốt", ""]
    for pid, part in parts.items():
        out.append(f"**{pid} — {part['mpn']}**")
        out.append("")
        out.append("| Thông số | Giá trị | Đơn vị | Nguồn |")
        out.append("|---|---|---|---|")
        for item in part.get("params", []):
            out.append(
                f"| {item['name']} | {item['value']} | {item.get('unit', '')} | "
                f"{item.get('source', '')} |"
            )
        out.append("")
    out += ["## 2. Module ngoài BOM", "",
            "| ID | Tên | Xác minh | Tài liệu | Ghi chú |",
            "|---|---|---|---|---|"]
    for eid, item in external.items():
        out.append(
            f"| {eid} | {item['name']} | {item.get('verified', 'no')} | "
            f"{item.get('datasheet', '') or '—'} | {item.get('notes', '')} |"
        )
    out += ["", "## 3. Vấn đề phát hiện", ""]
    if not issues:
        out.append("Không có vấn đề.")
    else:
        out += ["| Mức | Mục | Mô tả |", "|---|---|---|"]
        for level in ("blocker", "warn", "info"):
            for issue in issues:
                if issue.level == level:
                    out.append(f"| {issue.level} | {issue.item} | {issue.message} |")
    out += [
        "",
        "## 4. Cách dùng",
        "",
        "- `--strict` dùng làm cổng **trước khi đặt hàng**: còn blocker thì không đặt.",
        "- `--check` chỉ kiểm cấu trúc và file sinh; không chặn CI vì thiếu linh kiện chưa mua.",
        ("- Khi mở datasheet và xác nhận một thông số: sửa `verified` và `source` trong "
        "`spec/parts.toml`, chạy `--write`."),
        "",
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        parts, external = load_parts()
        bom = load_bom()
    except (OSError, ValueError, KeyError) as exc:
        print(f"LOI SO LINH KIEN: {exc}", file=sys.stderr)
        return 2
    issues = structural_issues(parts, external, bom) + design_issues(parts, external, bom)
    blockers = [i for i in issues if i.level == "blocker"]
    warns = [i for i in issues if i.level == "warn"]
    if args.check:
        structural = structural_issues(parts, external, bom)
        if structural:
            for issue in structural:
                print(f"LOI {issue.item}: {issue.message}", file=sys.stderr)
            return 1
        if not TARGET.exists():
            print("thieu hardware/parts-register.md; chay --write", file=sys.stderr)
            return 1
        current = TARGET.read_text(encoding="utf-8")
        if current != render():
            print("parts-register.md lech spec; chay --write", file=sys.stderr)
            return 1
        print(f"OK: so linh kien hop le; {len(blockers)} blocker, {len(warns)} canh bao")
        return 0
    if args.write:
        TARGET.write_text(render(), encoding="utf-8", newline="\n")
        print(f"ghi {TARGET.relative_to(ROOT)}")
        return 0
    for issue in issues:
        print(f"{issue.level.upper()} {issue.item}: {issue.message}")
    print(f"TONG: {len(blockers)} blocker, {len(warns)} canh bao")
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
