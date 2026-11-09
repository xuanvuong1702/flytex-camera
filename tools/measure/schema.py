"""Measurement row schema and validation for G0.

A row is either *measured* (``value`` holds a finite number and
``pass_fail`` is ``PASS`` or ``FAIL``) or *not measured yet* (``value`` is
empty and ``pass_fail`` is ``NA``).  A missing measurement must never be
written as ``0``: zero is a real number and would silently enter the
energy budget.

All exception messages are ASCII so they are safe to print on a Windows
console with a legacy code page.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields
from datetime import date

#: Measurement identifiers used by docs/08-kiem-chung.md.
ID_RE = re.compile(r"^M-\d{2,3}$")

#: Dates are ISO calendar dates, nothing else (no "20261109" shorthand).
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Plain decimal numbers only.  This rejects "nan", "inf" and Python's
#: underscore literals before they can reach the energy calculation.
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")

PASS_FAIL_VALUES = ("PASS", "FAIL", "NA")

#: Allowed units per quantity.  Add a quantity here only when a measurement
#: in docs/08 needs it; an empty unit is never valid for a measured row.
QUANTITY_UNITS: dict[str, tuple[str, ...]] = {
    "voltage": ("V", "mV"),
    "current": ("A", "mA", "uA"),
    "power": ("W", "mW"),
    "energy": ("Wh", "mWh"),
    "capacity": ("Ah", "mAh"),
    "time": ("s", "ms", "min", "h"),
    "latency": ("s", "ms"),
    "bandwidth": ("bps", "kbps", "Mbps"),
    "temperature": ("C", "degC", "\u00b0C"),
    "percent": ("%",),
    "count": ("count",),
    "boolean": ("bool",),
}

class MeasurementError(ValueError):
    """Raised when a measurement row is not valid."""


@dataclass
class Measurement:
    """One row of the G0 measurement table.

    ``value`` and ``uncertainty_pct`` are kept as the raw CSV text so that
    loading and saving round-trips exactly and so that *empty* stays
    distinguishable from ``0``.  Use :func:`value_as_float` after
    :func:`validate` when a number is needed.
    """

    id: str = ""
    date: str = ""
    board_rev: str = ""
    condition: str = ""
    instrument: str = ""
    quantity: str = ""
    value: str = ""
    unit: str = ""
    uncertainty_pct: str = ""
    pass_fail: str = "NA"
    notes: str = ""


#: Column order of the CSV files, matching the dataclass field order.
FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in fields(Measurement))


def _s(value: object) -> str:
    """Return a stripped string; ``None`` becomes the empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _check_number(raw: str, what: str) -> float:
    if not NUMBER_RE.match(raw):
        raise MeasurementError(f"{what} is not a finite number: {raw!r}")
    number = float(raw)
    if not math.isfinite(number):
        raise MeasurementError(f"{what} is not a finite number: {raw!r}")
    return number


def validate(m: Measurement) -> None:
    """Validate one row, raising :class:`MeasurementError` on the first error.

    Rules:
      * ``id`` matches ``M-xx`` / ``M-xxx``;
      * ``quantity`` is known and ``unit`` belongs to that quantity; a
        placeholder row (empty value + ``NA``) may omit both;
      * ``value`` is empty exactly when ``pass_fail`` is ``NA``; a non-empty
        value must be a finite decimal number, never ``nan`` / ``inf``;
      * ``uncertainty_pct`` is empty or a finite number in ``[0, 100]``;
      * ``date`` is empty or a real ISO date (``YYYY-MM-DD``);
      * ``pass_fail`` is one of PASS, FAIL, NA.
    """
    if m is None:
        raise MeasurementError("measurement is None")

    mid = _s(m.id)
    if not ID_RE.match(mid):
        raise MeasurementError(f"id is not M-xx or M-xxx: {mid!r}")

    pf = _s(m.pass_fail)
    if pf not in PASS_FAIL_VALUES:
        raise MeasurementError(
            f"pass_fail must be one of {', '.join(PASS_FAIL_VALUES)}: {pf!r}"
        )

    raw_value = _s(m.value)
    unmeasured = raw_value == "" and pf == "NA"
    if raw_value == "":
        if pf != "NA":
            raise MeasurementError(
                f"empty value requires pass_fail NA, got {pf!r} "
                "(a missing measurement must not be filled with 0)"
            )
    else:
        if pf == "NA":
            raise MeasurementError(
                "pass_fail NA requires an empty value; "
                "do not fill a missing measurement with 0"
            )
        _check_number(raw_value, "value")

    # A placeholder row (value empty, pass_fail NA) may omit quantity/unit;
    # as soon as there is a number, both are required and must agree.
    quantity = _s(m.quantity)
    unit = _s(m.unit)
    if quantity == "":
        if unit != "":
            raise MeasurementError(
                f"unit {unit!r} given without a quantity"
            )
        if not unmeasured:
            raise MeasurementError("quantity is required for a measured row")
    else:
        if quantity not in QUANTITY_UNITS:
            allowed = ", ".join(sorted(QUANTITY_UNITS))
            raise MeasurementError(
                f"unknown quantity {quantity!r}; allowed: {allowed}"
            )
        if unit not in QUANTITY_UNITS[quantity]:
            allowed = ", ".join(QUANTITY_UNITS[quantity])
            raise MeasurementError(
                f"unit {unit!r} is not allowed for quantity {quantity!r}; "
                f"allowed: {allowed}"
            )

    raw_unc = _s(m.uncertainty_pct)
    if raw_unc != "":
        unc = _check_number(raw_unc, "uncertainty_pct")
        if not 0.0 <= unc <= 100.0:
            raise MeasurementError(
                f"uncertainty_pct must be between 0 and 100, got {raw_unc!r}"
            )

    raw_date = _s(m.date)
    if raw_date != "":
        if not DATE_RE.match(raw_date):
            raise MeasurementError(
                f"date must be ISO YYYY-MM-DD or empty: {raw_date!r}"
            )
        try:
            date.fromisoformat(raw_date)
        except ValueError as exc:
            raise MeasurementError(
                f"date is not a real calendar date: {raw_date!r}"
            ) from exc


def value_as_float(m: Measurement) -> float | None:
    """Return the measured value, or ``None`` when the row is not measured."""
    validate(m)
    raw = _s(m.value)
    return None if raw == "" else float(raw)


def uncertainty_as_float(m: Measurement) -> float | None:
    """Return the uncertainty in percent, or ``None`` when it is empty."""
    validate(m)
    raw = _s(m.uncertainty_pct)
    return None if raw == "" else float(raw)


def is_measured(m: Measurement) -> bool:
    """True when the row carries a real number (and is not ``NA``)."""
    validate(m)
    return _s(m.value) != "" and _s(m.pass_fail) != "NA"
