"""Validation tests for tools.measure.schema."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.measure.schema import (  # noqa: E402
    FIELD_NAMES,
    Measurement,
    MeasurementError,
    is_measured,
    uncertainty_as_float,
    validate,
    value_as_float,
)


def make_row(**overrides: str) -> Measurement:
    values = {
        "id": "M-01",
        "date": "2026-11-09",
        "board_rev": "Rev0",
        "condition": "bench",
        "instrument": "PPK2",
        "quantity": "power",
        "value": "1.4",
        "unit": "W",
        "uncertainty_pct": "10",
        "pass_fail": "PASS",
        "notes": "",
    }
    values.update(overrides)
    return Measurement(**values)


class MeasurementSchemaTest(unittest.TestCase):
    def test_field_order_matches_csv_contract(self) -> None:
        self.assertEqual(
            FIELD_NAMES,
            (
                "id",
                "date",
                "board_rev",
                "condition",
                "instrument",
                "quantity",
                "value",
                "unit",
                "uncertainty_pct",
                "pass_fail",
                "notes",
            ),
        )

    def test_valid_measured_row(self) -> None:
        validate(make_row())

    def test_valid_unmeasured_row(self) -> None:
        validate(
            make_row(
                value="", uncertainty_pct="", pass_fail="NA", quantity="current",
                unit="mA",
            )
        )

    def test_date_may_be_empty(self) -> None:
        validate(make_row(date=""))

    def test_minimal_unmeasured_placeholder_is_valid(self) -> None:
        validate(Measurement(id="M-03"))

    def test_measured_row_requires_quantity(self) -> None:
        with self.assertRaises(MeasurementError):
            validate(Measurement(id="M-03", value="8", pass_fail="PASS"))

    def test_unit_without_quantity_rejected(self) -> None:
        with self.assertRaises(MeasurementError):
            validate(Measurement(id="M-03", unit="W"))

    def test_bad_id_rejected(self) -> None:
        for bad_id in ("M-1", "M-0001", "X-01", "", "M-"):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(MeasurementError):
                    validate(make_row(id=bad_id))

    def test_unknown_quantity_rejected(self) -> None:
        with self.assertRaises(MeasurementError) as ctx:
            validate(make_row(quantity="flux", unit="W"))
        self.assertIn("quantity", str(ctx.exception))

    def test_wrong_unit_for_quantity_rejected(self) -> None:
        with self.assertRaises(MeasurementError) as ctx:
            validate(make_row(quantity="power", unit="mA"))
        self.assertIn("unit", str(ctx.exception))

    def test_value_must_be_finite_number(self) -> None:
        for bad_value in ("nan", "inf", "-inf", "abc", "1_0", "1,4"):
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(MeasurementError):
                    validate(make_row(value=bad_value))

    def test_zero_is_a_real_measurement(self) -> None:
        # Zero is allowed when it is actually measured; it is forbidden only
        # as a stand-in for "not measured yet".
        validate(make_row(value="0", pass_fail="FAIL"))

    def test_empty_value_requires_na(self) -> None:
        with self.assertRaises(MeasurementError):
            validate(make_row(value="", pass_fail="PASS"))

    def test_na_requires_empty_value_and_never_zero(self) -> None:
        with self.assertRaises(MeasurementError) as ctx:
            validate(make_row(value="0", pass_fail="NA"))
        self.assertIn("0", str(ctx.exception))

    def test_bad_pass_fail_rejected(self) -> None:
        for bad in ("OK", "pass", "", "N/A"):
            with self.subTest(bad=bad):
                with self.assertRaises(MeasurementError):
                    validate(make_row(pass_fail=bad))

    def test_uncertainty_range(self) -> None:
        for good in ("0", "0.0", "100", "12.5"):
            with self.subTest(good=good):
                validate(make_row(uncertainty_pct=good))
        for bad in ("-0.1", "-1", "100.1", "1e3"):
            with self.subTest(bad=bad):
                with self.assertRaises(MeasurementError):
                    validate(make_row(uncertainty_pct=bad))

    def test_uncertainty_must_be_number(self) -> None:
        with self.assertRaises(MeasurementError):
            validate(make_row(uncertainty_pct="ten percent"))

    def test_uncertainty_may_be_empty(self) -> None:
        validate(make_row(uncertainty_pct=""))

    def test_bad_date_rejected(self) -> None:
        for bad_date in ("09/11/2026", "2026-13-01", "2026-02-30", "20261109"):
            with self.subTest(bad_date=bad_date):
                with self.assertRaises(MeasurementError):
                    validate(make_row(date=bad_date))

    def test_value_helpers(self) -> None:
        measured = make_row(value="2.30", uncertainty_pct="5")
        self.assertEqual(value_as_float(measured), 2.3)
        self.assertEqual(uncertainty_as_float(measured), 5.0)
        self.assertTrue(is_measured(measured))

        pending = make_row(value="", uncertainty_pct="", pass_fail="NA")
        self.assertIsNone(value_as_float(pending))
        self.assertIsNone(uncertainty_as_float(pending))
        self.assertFalse(is_measured(pending))

    def test_helpers_revalidate(self) -> None:
        with self.assertRaises(MeasurementError):
            value_as_float(make_row(value="nan"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
