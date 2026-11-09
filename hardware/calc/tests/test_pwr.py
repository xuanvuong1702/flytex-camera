"""Test các phép tính thiết kế PWR."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.calc import cli, design, pwr, report


class SeriesTests(unittest.TestCase):
    def test_e96_values_are_sorted_and_bounded(self) -> None:
        values = pwr.e96_values(1_000, 10_000)
        self.assertTrue(values)
        self.assertEqual(values, sorted(values))
        self.assertGreaterEqual(min(values), 1_000)
        self.assertLessEqual(max(values), 10_000)

    def test_e96_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            pwr.e96_values(10, 1)


class DividerTests(unittest.TestCase):
    def test_boost_divider_error_is_small(self) -> None:
        divider = pwr.choose_divider(5.0, 1.204)
        self.assertLess(divider.error_pct, 1.0)
        self.assertAlmostEqual(divider.vout_v, 5.0, delta=0.05)
        self.assertGreater(divider.ratio, 3.0)
        self.assertGreaterEqual(divider.bottom_ohm, 10_000)

    def test_divider_rejects_vout_below_vref(self) -> None:
        with self.assertRaises(ValueError):
            pwr.choose_divider(1.0, 1.204)


class BoostTests(unittest.TestCase):
    def test_currents_at_weak_battery(self) -> None:
        current = pwr.boost_currents(3.0, 5.0, 3.0, 0.9, 597_000, 1.2e-6)
        self.assertAlmostEqual(current.duty, 0.46, delta=0.01)
        self.assertAlmostEqual(current.input_a, 5.56, delta=0.03)
        self.assertAlmostEqual(current.ripple_pp_a, 1.93, delta=0.05)
        self.assertAlmostEqual(current.peak_a, 6.52, delta=0.1)

    def test_currents_at_nominal_are_lower(self) -> None:
        weak = pwr.boost_currents(3.0, 5.0, 3.0, 0.9, 597_000, 1.2e-6)
        nominal = pwr.boost_currents(3.2, 5.0, 3.0, 0.9, 597_000, 1.2e-6)
        self.assertLess(nominal.peak_a, weak.peak_a)
        self.assertLess(nominal.duty, weak.duty)

    def test_peak_has_margin_over_saturation(self) -> None:
        current = pwr.boost_currents(3.0, 5.0, 3.0, 0.9, 597_000, 1.2e-6)
        self.assertLessEqual(current.peak_a * 1.2, design.BOOST["inductor_isat_a"])

    def test_boost_rejects_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            pwr.boost_currents(5.0, 5.0, 1.0, 0.9, 500_000, 1e-6)
        with self.assertRaises(ValueError):
            pwr.boost_currents(3.0, 5.0, 1.0, 0.0, 500_000, 1e-6)


class ChargerTests(unittest.TestCase):
    def test_linear_loss(self) -> None:
        self.assertAlmostEqual(pwr.linear_charger_loss_w(5.0, 3.6, 1.5), 2.1)

    def test_linear_loss_rejects_reverse(self) -> None:
        with self.assertRaises(ValueError):
            pwr.linear_charger_loss_w(3.6, 5.0, 1.0)

    def test_charge_time_15ah_knows_efficiency(self) -> None:
        hours = pwr.charge_time_h(15.0, 1.5, 0.2, 1.0, 0.9)
        self.assertAlmostEqual(hours, 8.89, delta=0.05)

    def test_charge_time_invalid_soc(self) -> None:
        with self.assertRaises(ValueError):
            pwr.charge_time_h(15.0, 1.5, 0.9, 0.5)


class NtcTests(unittest.TestCase):
    def test_resistance_at_25c(self) -> None:
        self.assertAlmostEqual(pwr.ntc_resistance_ohm(25.0), 10_000, delta=1)

    def test_resistance_at_40c(self) -> None:
        self.assertAlmostEqual(pwr.ntc_resistance_ohm(40.0), 5_300, delta=120)

    def test_resistance_decreases_with_temperature(self) -> None:
        values = [pwr.ntc_resistance_ohm(t) for t in (0, 10, 25, 40, 60)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_ratio_at_25c(self) -> None:
        self.assertAlmostEqual(pwr.ntc_ratio(25.0), 10_000 / 17_150, delta=0.002)

    def test_cutoff_temperatures(self) -> None:
        hot = pwr.ntc_temperature_at_ratio(0.425)
        cold = pwr.ntc_temperature_at_ratio(0.475)
        self.assertAlmostEqual(hot, 40.1, delta=0.6)
        self.assertAlmostEqual(cold, 35.2, delta=0.6)
        self.assertLess(hot, 42.0)
        self.assertGreater(cold, 34.0)

    def test_ratio_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            pwr.ntc_temperature_at_ratio(1.5)


class AdcTests(unittest.TestCase):
    def test_battery_adc_values(self) -> None:
        adc = pwr.battery_adc(3.65, 3.3, 12, 100_000, 100_000)
        self.assertAlmostEqual(adc.divider_ratio, 2.0)
        self.assertAlmostEqual(adc.adc_mv_at_max, 1825.0, delta=0.5)
        self.assertAlmostEqual(adc.mv_per_lsb, 1.61, delta=0.02)
        self.assertAlmostEqual(adc.headroom_v, 1.475, delta=0.01)

    def test_battery_adc_rejects_overvoltage(self) -> None:
        with self.assertRaises(ValueError):
            pwr.battery_adc(3.65, 3.3, 12, 10_000, 100_000)

    def test_battery_adc_rejects_bad_bits(self) -> None:
        with self.assertRaises(ValueError):
            pwr.battery_adc(3.65, 3.3, 4, 100_000, 100_000)


class ThermalAndPackTests(unittest.TestCase):
    def test_thermal_rise(self) -> None:
        rise = pwr.thermal_rise_c(3.8, 0.0372, 8.0)
        self.assertAlmostEqual(rise, 12.77, delta=0.1)
        surface = pwr.surface_temp_c(3.8, 0.0372, 45.0, 8.0)
        self.assertAlmostEqual(surface, 57.77, delta=0.1)

    def test_thermal_invalid(self) -> None:
        with self.assertRaises(ValueError):
            pwr.thermal_rise_c(-1, 0.0372)

    def test_pack_energy(self) -> None:
        self.assertAlmostEqual(pwr.pack_wh(15, 3.2), 48.0)
        self.assertAlmostEqual(pwr.pack_wh(15, 3.2, 0.85), 40.8, delta=0.01)
        self.assertAlmostEqual(pwr.pack_wh(10, 3.2), 32.0)

    def test_pack_invalid(self) -> None:
        with self.assertRaises(ValueError):
            pwr.pack_wh(0, 3.2)


class DesignTests(unittest.TestCase):
    def test_all_checks_pass(self) -> None:
        checks = design.checks()
        failed = [check.name for check in checks if not check.passed]
        self.assertEqual(failed, [])
        self.assertGreaterEqual(len(checks), 8)

    def test_report_has_required_sections_and_no_failure(self) -> None:
        text = report.render()
        for heading in ("## 2. Boost 5 V", "## 4. Cắt sạc", "## 8. Kiểm tra tự động"):
            self.assertIn(heading, text)
        self.assertNotIn("**KHÔNG ĐẠT**", text)
        self.assertIn("không phải số đo", text)

    def test_cli_check_matches_committed_file(self) -> None:
        self.assertEqual(cli.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
