"""Markdown report for the G0 energy gate.

The report is written to a UTF-8 file; it is never printed as Vietnamese to
the Windows console by the CLI.  Every number carries enough precision that a
failing margin cannot look like a passing one after rounding.
"""

from __future__ import annotations

from datetime import date

from .energy import (
    BENCH_CAPACITY_AH,
    TARGET_MARGIN,
    EnergyError,
    Pack,
    Scenario,
    correction_note,
    margin,
)
from .schema import Measurement, validate


def _cell(text: object) -> str:
    """Escape a value for a markdown table cell."""
    value = "" if text is None else str(text)
    value = value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    return value.strip()


def _fmt(value: float, digits: int = 2) -> str:
    """Fixed decimals with a dot decimal separator."""
    return f"{value:.{digits}f}"


def _validation_line(scenario: Scenario, pack: Pack) -> str | None:
    """Return a failure explanation, or ``None`` when the margin passes."""
    if scenario.power_w <= 0.0:
        return (
            f'- Kịch bản "{scenario.name}": công suất 0 W, '
            "không tính được hệ số dư (không chia cho 0)."
        )
    if scenario.duration_h <= 0.0:
        return (
            f'- Kịch bản "{scenario.name}": thời lượng 0 h, '
            "không tính được hệ số dư (không chia cho 0)."
        )

    try:
        factor = margin(pack.usable_wh, scenario.power_w, scenario.duration_h)
    except EnergyError as exc:
        return f'- Kịch bản "{scenario.name}": không tính được hệ số dư: {exc}.'
    if factor >= TARGET_MARGIN:
        return None

    needed_usable_wh = (
        scenario.power_w * scenario.duration_h * TARGET_MARGIN
    )
    needed_ah = needed_usable_wh / (
        pack.nominal_v * pack.usable_fraction
    )
    surplus_pct = (factor - 1.0) * 100.0
    return (
        f'- Kịch bản "{scenario.name}": KHÔNG ĐẠT, hệ số dư '
        f"{_fmt(factor, 3)} (dư {_fmt(surplus_pct, 1)} %). "
        f"Cần {_fmt(needed_usable_wh, 2)} Wh dùng được; "
        f"với pack {_fmt(pack.nominal_v, 1)} V và "
        f"{_fmt(pack.usable_fraction * 100.0, 0)} % dùng được, "
        f"cần {_fmt(needed_ah, 1)} Ah "
        f"(pack {_fmt(pack.capacity_ah, 1)} Ah)."
    )


def render_markdown(
    scenarios: list[Scenario],
    measurements: list[Measurement],
    pack: Pack,
    *,
    today: date | None = None,
) -> str:
    """Render the full G0 energy report as markdown (UTF-8, LF)."""
    if not isinstance(pack, Pack):
        raise TypeError("pack must be tools.measure.energy.Pack")
    scenario_list = list(scenarios)
    measurement_list = list(measurements)
    for measurement in measurement_list:
        validate(measurement)

    report_date = today if today is not None else date.today()
    lines: list[str] = []

    lines.append("# Báo cáo năng lượng G0 — Flytex Camera")
    lines.append("")
    lines.append(f"- Ngày: {report_date.isoformat()}")
    lines.append(
        f"- Pack: {_fmt(pack.capacity_ah, 1)} Ah × "
        f"{_fmt(pack.nominal_v, 1)} V = {_fmt(pack.nominal_wh, 1)} Wh "
        f"danh định; dùng được {_fmt(pack.usable_fraction * 100.0, 0)} % = "
        f"{_fmt(pack.usable_wh, 1)} Wh."
    )
    lines.append(
        "- Nguồn: docs/02 §3; kịch bản ghi CHƯA ĐO là ước tính CAM4G, "
        "không dùng để nghiệm thu."
    )
    lines.append("")
    lines.append(
        "> **CẢNH BÁO:** Số liệu có nhãn CHƯA ĐO / ƯỚC TÍNH không được "
        "dùng làm tiêu chí nghiệm thu."
    )
    lines.append("")

    lines.append("## Quy đổi năng lượng")
    lines.append("")
    lines.append(correction_note())
    lines.append("")

    lines.append("## Bảng kịch bản")
    lines.append("")
    lines.append(
        "| Kịch bản | Trạng thái | Công suất (W) | Thời lượng (h) | "
        "Năng lượng (Wh) | % pack dùng được | Hệ số dư | "
        "Dư mục tiêu 30 % | Nguồn |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|"
    )
    if not scenario_list:
        lines.append("| _(không có kịch bản)_ | | | | | | | | |")
    for scenario in scenario_list:
        energy_wh = scenario.energy_wh
        if pack.usable_wh > 0.0:
            pct_pack = energy_wh / pack.usable_wh * 100.0
            pct_text = _fmt(pct_pack, 1)
        else:  # pragma: no cover - Pack guarantees usable_wh > 0
            pct_text = "n/a"

        if scenario.power_w <= 0.0 or scenario.duration_h <= 0.0:
            factor_text = "n/a"
            status = "KHÔNG TÍNH ĐƯỢC"
        else:
            factor = margin(
                pack.usable_wh, scenario.power_w, scenario.duration_h
            )
            factor_text = _fmt(factor, 3)
            status = "ĐẠT" if factor >= TARGET_MARGIN else "KHÔNG ĐẠT"

        source = "ĐÃ ĐO" if scenario.measured else "CHƯA ĐO (ước tính)"
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(scenario.name),
                    _cell(scenario.state),
                    _fmt(scenario.power_w, 2),
                    _fmt(scenario.duration_h, 1),
                    _fmt(energy_wh, 2),
                    pct_text,
                    factor_text,
                    status,
                    source,
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("## Bảng phép đo")
    lines.append("")
    if not measurement_list:
        lines.append("_(chưa có phép đo)_")
    else:
        lines.append(
            "| ID | Ngày | Rev board | Điều kiện | Dụng cụ | Giá trị | "
            "± % | Kết quả | Ghi chú |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for item in measurement_list:
            if item.value.strip() == "":
                value_text = "CHƯA ĐO"
            else:
                value_text = f"{item.value.strip()} {item.unit}".strip()
            uncertainty = (
                f"{item.uncertainty_pct.strip()} %"
                if item.uncertainty_pct.strip()
                else "-"
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(item.id),
                        _cell(item.date) or "-",
                        _cell(item.board_rev) or "-",
                        _cell(item.condition) or "-",
                        _cell(item.instrument) or "-",
                        value_text,
                        uncertainty,
                        _cell(item.pass_fail),
                        _cell(item.notes) or "-",
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.append("## Kết luận tự động")
    lines.append("")
    lines.append(
        f"- Mục tiêu: hệ số dư ≥ {_fmt(TARGET_MARGIN, 2)} "
        "(tức dư 30 %) cho mọi kịch bản."
    )

    failures = 0
    for scenario in scenario_list:
        explanation = _validation_line(scenario, pack)
        if explanation is not None:
            failures += 1
            lines.append(explanation)

    if scenario_list and failures == 0:
        lines.append(
            "- Mọi kịch bản đều đạt dư ≥ 30 % theo số liệu hiện có."
        )

    measured_scenarios = [s for s in scenario_list if s.measured]
    if scenario_list and not measured_scenarios:
        lines.append("- **Không có phép đo thật: chưa được qua G0.**")

    # The v0.1 bench pack is still useful as a reference: it is why the
    # project moved to 15 Ah.  Keep the shortfall visible on every report.
    if abs(pack.capacity_ah - BENCH_CAPACITY_AH) > 1e-9:
        bench_pack = Pack(
            BENCH_CAPACITY_AH, pack.nominal_v, pack.usable_fraction
        )
        bench_lines = [
            explanation
            for explanation in (
                _validation_line(scenario, bench_pack)
                for scenario in scenario_list
            )
            if explanation is not None
        ]
        if bench_lines:
            lines.append("")
            lines.append(
                f"### Tham chiếu pack {BENCH_CAPACITY_AH:.0f} Ah "
                "(bench, không dùng nghiệm thu)"
            )
            lines.extend(bench_lines)

    failed_measurements = sum(
        1 for item in measurement_list if item.pass_fail == "FAIL"
    )
    if failed_measurements:
        lines.append(
            f"- Có {failed_measurements} phép đo FAIL; xem bảng phép đo."
        )

    lines.append("")
    return "\n".join(lines)
