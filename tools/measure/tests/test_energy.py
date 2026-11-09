"""Energy maths tests: Wh, Ah, margin, uncertainty propagation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure.energy import (
    TARGET_MARGIN,
    EnergyError,
    Pack,
    Scenario,
    battery_life_h,
    correction_note,
    default_g0_scenarios,
    margin,
    nominal_pack_energy_wh,
    pack_energy_wh,
    propagate,
)


class PackEnergyTest(unittest.TestCase):
    def test_ten_ah_lfp_is_32_wh_not_37(self) -> None:
        self.assertAlmostEqual(nominal_pack_energy_wh(10, 3.2), 32.0, places=9)
        self.assertAlmostEqual(
            pack_energy_wh(10, 3.2, usable_fraction=1.0), 32.0, places=9
        )

    def test_fifteen_ah_lfp_is_48_wh(self) -> None:
        self.assertAlmostEqual(nominal_pack_energy_wh(15, 3.2), 48.0, places=9)
        self.assertAlmostEqual(
            pack_energy_wh(15, 3.2, usable_fraction=1.0), 48.0, places=9
        )

    def test_default_usable_fraction_is_85_percent(self) -> None:
        self.assertAlmostEqual(pack_energy_wh(10, 3.2), 27.2, places=9)
        self.assertAlmostEqual(pack_energy_wh(15, 3.2), 40.8, places=9)

    def test_pack_dataclass(self) -> None:
        pack = Pack(10)
        self.assertAlmostEqual(pack.nominal_wh, 32.0, places=9)
        self.assertAlmostEqual(pack.usable_wh, 27.2, places=9)

    def test_invalid_pack_inputs(self) -> None:
        for args in (
            (0, 3.2),
            (-1, 3.2),
            (10, 0),
            (10, -3.2),
        ):
            with self.subTest(args=args), self.assertRaises(EnergyError):
                pack_energy_wh(*args)
        with self.assertRaises(EnergyError):
            pack_energy_wh(10, 3.2, usable_fraction=1.5)
        with self.assertRaises(EnergyError):
            pack_energy_wh(10, 3.2, usable_fraction=0)


class MarginTest(unittest.TestCase):
    def test_night_scenario_with_10_ah_is_below_target(self) -> None:
        factor = margin(Pack(10).usable_wh, 3.8, 7.0)
        self.assertAlmostEqual(factor, 27.2 / 26.6, places=9)
        self.assertLess(factor, TARGET_MARGIN)

    def test_night_scenario_with_15_ah_passes(self) -> None:
        factor = margin(Pack(15).usable_wh, 3.8, 7.0)
        self.assertAlmostEqual(factor, 40.8 / 26.6, places=9)
        self.assertGreaterEqual(factor, TARGET_MARGIN)

    def test_margin_at_exact_30_percent(self) -> None:
        required = 3.8 * 7.0 * TARGET_MARGIN
        self.assertAlmostEqual(margin(required, 3.8, 7.0), TARGET_MARGIN,
                               places=9)

    def test_zero_power_raises_clear_error(self) -> None:
        with self.assertRaises(EnergyError) as ctx:
            margin(27.2, 0.0, 7.0)
        self.assertIn("0", str(ctx.exception))

    def test_zero_duration_raises(self) -> None:
        with self.assertRaises(EnergyError):
            margin(27.2, 1.4, 0.0)

    def test_battery_life(self) -> None:
        self.assertAlmostEqual(battery_life_h(27.2, 1.4), 27.2 / 1.4, places=9)
        self.assertAlmostEqual(battery_life_h(27.2, 3.8), 27.2 / 3.8, places=9)

    def test_battery_life_zero_load_raises(self) -> None:
        with self.assertRaises(EnergyError):
            battery_life_h(27.2, 0.0)


class PropagationTest(unittest.TestCase):
    def test_propagate_ten_percent(self) -> None:
        low, high = propagate(3.8, 10.0)
        self.assertAlmostEqual(low, 3.42, places=9)
        self.assertAlmostEqual(high, 4.18, places=9)

    def test_propagate_zero_percent(self) -> None:
        self.assertEqual(propagate(2.3, 0.0), (2.3, 2.3))

    def test_propagate_rejects_bad_percent(self) -> None:
        for pct in (-1.0, 101.0, float("nan")):
            with self.subTest(pct=pct), self.assertRaises(EnergyError):
                propagate(1.0, pct)


class ScenarioTest(unittest.TestCase):
    def test_scenario_energy_and_range(self) -> None:
        scenario = Scenario("night", "S3+IR", 3.8, 7 * 3600, 10.0, False)
        self.assertAlmostEqual(scenario.duration_h, 7.0, places=9)
        self.assertAlmostEqual(scenario.energy_wh, 26.6, places=9)
        low, high = scenario.energy_range_wh()
        self.assertAlmostEqual(low, 3.42 * 7.0, places=9)
        self.assertAlmostEqual(high, 4.18 * 7.0, places=9)

    def test_default_g0_scenarios_are_estimates(self) -> None:
        scenarios = default_g0_scenarios()
        self.assertEqual(len(scenarios), 3)
        self.assertEqual([s.power_w for s in scenarios], [1.4, 2.3, 3.8])
        self.assertTrue(all(s.duration_h == 7.0 for s in scenarios))
        self.assertTrue(all(not s.measured for s in scenarios))

    def test_negative_scenario_inputs_rejected(self) -> None:
        with self.assertRaises(EnergyError):
            Scenario("bad", "S0", -1.0, 3600)
        with self.assertRaises(EnergyError):
            Scenario("bad", "S0", 1.0, -1)
        with self.assertRaises(EnergyError):
            Scenario("bad", "S0", 1.0, 3600, 101)


class CorrectionNoteTest(unittest.TestCase):
    def test_note_mentions_32_and_37_wh(self) -> None:
        note = correction_note()
        self.assertIn("32", note)
        self.assertIn("37", note)
        self.assertIn("27.2", note)
        self.assertIn("CAM4G", note)


if __name__ == "__main__":
    unittest.main(verbosity=2)
