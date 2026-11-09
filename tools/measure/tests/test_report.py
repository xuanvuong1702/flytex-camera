"""Markdown report tests: warnings, scenario table, automatic conclusion."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure import csvio  # noqa: E402
from tools.measure.energy import Pack, Scenario, default_g0_scenarios  # noqa: E402
from tools.measure.report import render_markdown  # noqa: E402
from tools.measure.schema import Measurement, MeasurementError  # noqa: E402

SAMPLES = REPO_ROOT / "tools" / "measure" / "samples"
WARNING = (
    "Số liệu có nhãn CHƯA ĐO / ƯỚC TÍNH không được dùng làm "
    "tiêu chí nghiệm thu"
)


def render_10ah(measurements: list[Measurement] | None = None,
                scenarios: list[Scenario] | None = None) -> str:
    return render_markdown(
        scenarios if scenarios is not None else default_g0_scenarios(),
        measurements or [],
        Pack(10),
        today=date(2026, 11, 9),
    )


class ReportWarningTest(unittest.TestCase):
    def test_report_always_contains_estimate_warning(self) -> None:
        text = render_10ah()
        self.assertIn(WARNING, text)
        self.assertIn("CHƯA ĐO", text)

    def test_unmeasured_scenarios_say_g0_not_passed(self) -> None:
        self.assertIn("Không có phép đo thật: chưa được qua G0", render_10ah())

    def test_measured_scenarios_drop_g0_line(self) -> None:
        scenarios = [
            Scenario("Ghi cục bộ", "S2", 1.4, 7 * 3600, 10.0, True)
        ]
        self.assertNotIn("Không có phép đo thật", render_10ah(scenarios=scenarios))

    def test_report_date_is_iso(self) -> None:
        self.assertIn("- Ngày: 2026-11-09", render_10ah())

    def test_pack_metadata_uses_32_and_27_2_wh(self) -> None:
        text = render_10ah()
        self.assertIn("32.0 Wh", text)
        self.assertIn("27.2 Wh", text)


class ReportScenarioTest(unittest.TestCase):
    def test_night_scenario_fails_and_needs_12_7_ah(self) -> None:
        text = render_10ah()
        self.assertIn("KHÔNG ĐẠT", text)
        self.assertIn("12.7 Ah", text)

    def test_15_ah_pack_passes_night_scenario(self) -> None:
        text = render_markdown(
            default_g0_scenarios(), [], Pack(15), today=date(2026, 11, 9)
        )
        self.assertIn("Mọi kịch bản đều đạt", text)
        self.assertIn("40.8 Wh", text)
        # The night row passes with 15 Ah...
        self.assertIn(
            "| 3.80 | 7.0 | 26.60 | 65.2 | 1.534 | ĐẠT |", text
        )
        # ...while the 10 Ah bench reference still shows why 15 Ah was chosen.
        self.assertIn("Tham chiếu pack 10 Ah", text)
        self.assertIn("12.7 Ah", text)

    def test_bench_reference_is_omitted_for_10_ah(self) -> None:
        self.assertNotIn("Tham chiếu pack 10 Ah", render_10ah())

    def test_zero_power_does_not_crash_and_is_reported(self) -> None:
        scenarios = [Scenario("Zero", "S0", 0.0, 7 * 3600)]
        text = render_10ah(scenarios=scenarios)
        self.assertIn("KHÔNG TÍNH ĐƯỢC", text)
        self.assertIn("không tính được hệ số dư", text)

    def test_zero_duration_does_not_crash(self) -> None:
        scenarios = [Scenario("Zero hours", "S0", 1.4, 0.0)]
        text = render_10ah(scenarios=scenarios)
        self.assertIn("KHÔNG TÍNH ĐƯỢC", text)


class ReportMeasurementTest(unittest.TestCase):
    def test_measurement_table_and_fail_count(self) -> None:
        rows = csvio.load(SAMPLES / "g0-example.csv")
        text = render_10ah(rows)
        self.assertIn("| M-01 |", text)
        self.assertIn("1.35 W", text)
        self.assertIn("DU LIEU MINH HOA - KHONG PHAI DO", text)
        self.assertIn("Có 1 phép đo FAIL", text)

    def test_empty_measurement_table(self) -> None:
        self.assertIn("_(chưa có phép đo)_", render_10ah())

    def test_pipes_in_notes_are_escaped(self) -> None:
        rows = [
            Measurement(
                id="M-03",
                quantity="latency",
                unit="s",
                value="8",
                pass_fail="PASS",
                notes="a|b",
            )
        ]
        self.assertIn("a\\|b", render_10ah(rows))

    def test_invalid_measurement_raises(self) -> None:
        rows = [Measurement(id="M-1", quantity="power", unit="W")]
        with self.assertRaises(MeasurementError):
            render_10ah(rows)

    def test_pack_must_be_pack(self) -> None:
        with self.assertRaises(TypeError):
            render_markdown([], [], 27.2)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
