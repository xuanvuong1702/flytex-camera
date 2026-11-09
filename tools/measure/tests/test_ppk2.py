"""Test nhập CSV PPK2 và chuyển thành dòng đo hợp lệ."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure.ppk2 import (  # noqa: E402
    Ppk2Error,
    load,
    parse_csv,
    to_measurements,
)
from tools.measure.schema import Measurement, validate  # noqa: E402

SAMPLE_SEMICOLON = """Time (s);Current (mA);Voltage (V)
0;1,0;3,7
1;1,0;3,7
2;1,0;3,7
3;1,0;3,7
4;1,0;3,7
5;1,0;3,7
6;1,0;3,7
7;1,0;3,7
8;1,0;3,7
9;1,0;3,7
10;1,0;3,7
"""


class ParseTests(unittest.TestCase):
    def test_semicolon_and_comma_decimal(self) -> None:
        trace = parse_csv(SAMPLE_SEMICOLON)
        self.assertEqual(len(trace.samples), 11)
        self.assertAlmostEqual(trace.duration_s, 10.0)
        self.assertAlmostEqual(trace.mean_ma, 1.0)
        self.assertAlmostEqual(trace.charge_mah, 10.0 / 3.6, places=4)
        self.assertAlmostEqual(trace.energy_mwh or 0.0, 3.7 * 10.0 / 3.6, places=4)

    def test_comma_delimiter_and_units(self) -> None:
        text = """Time (ms),Current (A),Voltage (mV)
0,0.010,3700
1000,0.010,3700
2000,0.010,3700
"""
        trace = parse_csv(text)
        self.assertAlmostEqual(trace.duration_s, 2.0)
        self.assertAlmostEqual(trace.mean_ma, 10.0)
        self.assertAlmostEqual(trace.energy_mwh or 0.0, 3.7 * 10.0 * 2.0 / 3.6, places=4)

    def test_without_voltage(self) -> None:
        text = """Time (s),Current (mA)
0,2
1,4
2,6
"""
        trace = parse_csv(text)
        self.assertIsNone(trace.energy_mwh)
        self.assertAlmostEqual(trace.mean_ma, 4.0)

    def test_partial_voltage_column(self) -> None:
        text = """Time (s),Current (mA),Voltage (V)
0,1,3.7
1,1,
2,1,3.7
"""
        trace = parse_csv(text)
        self.assertIsNone(trace.energy_mwh)

    def test_bad_header(self) -> None:
        with self.assertRaises(Ppk2Error):
            parse_csv("a,b,c\n1,2,3\n")

    def test_empty_file(self) -> None:
        with self.assertRaises(Ppk2Error):
            parse_csv("   \n")

    def test_unknown_unit(self) -> None:
        with self.assertRaises(Ppk2Error):
            parse_csv("Time (fortnight),Current (mA)\n0,1\n")

    def test_skips_bad_rows(self) -> None:
        text = """Time (s),Current (mA)
0,1
1,khong-phai-so
2,3
"""
        trace = parse_csv(text)
        self.assertEqual(len(trace.samples), 2)
        self.assertAlmostEqual(trace.duration_s, 2.0)

    def test_nonzero_start_is_normalised(self) -> None:
        text = """Time (s),Current (mA)
100,1
101,1
102,1
"""
        trace = parse_csv(text)
        self.assertAlmostEqual(trace.samples[0][0], 0.0)
        self.assertAlmostEqual(trace.duration_s, 2.0)

    def test_load_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            path.write_text(SAMPLE_SEMICOLON, encoding="utf-8")
            trace = load(path)
            self.assertEqual(len(trace.samples), 11)


class MeasurementConversionTests(unittest.TestCase):
    def test_rows_are_valid_for_schema(self) -> None:
        trace = parse_csv(SAMPLE_SEMICOLON)
        rows = to_measurements(trace, "M-01", condition="eco, 24h", board_rev="rev0")
        self.assertEqual(len(rows), 3)
        quantities = {row["quantity"] for row in rows}
        self.assertEqual(quantities, {"current", "capacity", "energy"})
        for row in rows:
            measurement = Measurement(**row)
            validate(measurement)

    def test_rows_use_measured_state(self) -> None:
        trace = parse_csv(SAMPLE_SEMICOLON)
        row = to_measurements(trace, "M-02")[0]
        self.assertEqual(row["unit"], "mA")
        self.assertAlmostEqual(float(row["value"]), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
