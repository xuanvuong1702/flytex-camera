"""Energy budget maths for the Flytex Camera G0 gate.

The reference numbers come from docs/02-thiet-ke-nguon.md section 3:
a 1S LFP pack is 3.2 V nominal, so 10 Ah is **32 Wh nominal**, not the
37 Wh that CAM4G quoted for a 3.7 V Li-ion pack.  With 85 % usable the
10 Ah pack gives 27.2 Wh.

A margin is expressed as a factor: ``available / required``.  The project
target is a factor of at least 1.30 (30 % surplus) on every scenario.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Minimum surplus factor for a scenario to pass (docs/02 section 3).
TARGET_MARGIN = 1.30

#: Nominal voltage of the 1S LFP pack used by this project.
LFP_NOMINAL_V = 3.2

#: Fraction of the nominal pack energy that may be used (docs/02 section 3).
DEFAULT_USABLE_FRACTION = 0.85

#: Bench pack from the v0.1 draft; it is kept as a reference, not for
#: acceptance.  The night scenario needs 12.7 Ah to reach a 30 % margin.
BENCH_CAPACITY_AH = 10.0


class EnergyError(ValueError):
    """Raised for invalid energy inputs (including division by zero)."""


def _number(name: str, value: object, *, minimum: float | None = None,
            maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EnergyError(f"{name} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise EnergyError(f"{name} must be finite, got {value!r}")
    if minimum is not None and number < minimum:
        raise EnergyError(f"{name} must be >= {minimum}, got {value!r}")
    if maximum is not None and number > maximum:
        raise EnergyError(f"{name} must be <= {maximum}, got {value!r}")
    return number


@dataclass(frozen=True)
class Scenario:
    """A load scenario for the energy budget.

    ``duration_s`` is in seconds (7 hours = 25200 s).  ``measured`` is False
    for the CAM4G-derived estimates and must be True only when the power
    figure comes from a real G0 measurement (M-01).
    """

    name: str
    state: str
    power_w: float
    duration_s: float
    uncertainty_pct: float = 0.0
    measured: bool = False

    def __post_init__(self) -> None:
        _number("power_w", self.power_w, minimum=0.0)
        _number("duration_s", self.duration_s, minimum=0.0)
        _number("uncertainty_pct", self.uncertainty_pct,
                minimum=0.0, maximum=100.0)

    @property
    def duration_h(self) -> float:
        return float(self.duration_s) / 3600.0

    @property
    def energy_wh(self) -> float:
        return float(self.power_w) * self.duration_h

    def energy_range_wh(self) -> tuple[float, float]:
        """Energy interval implied by ``uncertainty_pct``."""
        low_w, high_w = propagate(self.power_w, self.uncertainty_pct)
        return low_w * self.duration_h, high_w * self.duration_h


@dataclass(frozen=True)
class Pack:
    """A 1S LFP pack described by capacity, nominal voltage and usable share."""

    capacity_ah: float
    nominal_v: float = LFP_NOMINAL_V
    usable_fraction: float = DEFAULT_USABLE_FRACTION

    def __post_init__(self) -> None:
        # pack_energy_wh performs the range checks.
        pack_energy_wh(self.capacity_ah, self.nominal_v, self.usable_fraction)

    @property
    def nominal_wh(self) -> float:
        return nominal_pack_energy_wh(self.capacity_ah, self.nominal_v)

    @property
    def usable_wh(self) -> float:
        return pack_energy_wh(self.capacity_ah, self.nominal_v,
                              self.usable_fraction)


def pack_energy_wh(capacity_ah: float, nominal_v: float,
                   usable_fraction: float = DEFAULT_USABLE_FRACTION) -> float:
    """Return the **usable** pack energy in Wh.

    ``capacity_ah * nominal_v`` is the nominal energy; multiplying by
    ``usable_fraction`` (default 0.85) gives what the firmware may actually
    draw.  For the nominal figure call
    ``pack_energy_wh(10, 3.2, usable_fraction=1.0)`` or use
    :func:`nominal_pack_energy_wh`.

    >>> pack_energy_wh(10, 3.2, usable_fraction=1.0)
    32.0
    >>> round(pack_energy_wh(10, 3.2), 1)
    27.2
    """
    cap = _number("capacity_ah", capacity_ah, minimum=0.0)
    volts = _number("nominal_v", nominal_v, minimum=0.0)
    fraction = _number("usable_fraction", usable_fraction,
                       minimum=0.0, maximum=1.0)
    if cap <= 0.0:
        raise EnergyError(f"capacity_ah must be > 0, got {capacity_ah!r}")
    if volts <= 0.0:
        raise EnergyError(f"nominal_v must be > 0, got {nominal_v!r}")
    if fraction <= 0.0:
        raise EnergyError(
            f"usable_fraction must be > 0, got {usable_fraction!r}"
        )
    return cap * volts * fraction


def nominal_pack_energy_wh(capacity_ah: float, nominal_v: float) -> float:
    """Return the nominal pack energy in Wh (before the usable derating).

    10 Ah LFP at 3.2 V -> 32 Wh; 15 Ah -> 48 Wh.  This is deliberately
    separate from :func:`pack_energy_wh` so nobody mistakes the CAM4G 37 Wh
    Li-ion figure for an LFP figure.
    """
    return pack_energy_wh(capacity_ah, nominal_v, usable_fraction=1.0)


def battery_life_h(pack_wh: float, load_w: float) -> float:
    """Hours of runtime for ``pack_wh`` usable energy at a constant load."""
    energy = _number("pack_wh", pack_wh, minimum=0.0)
    load = _number("load_w", load_w, minimum=0.0)
    if load <= 0.0:
        raise EnergyError(
            "load_w is 0 W: battery life is undefined (no division by zero)"
        )
    return energy / load


def margin(pack_wh: float, load_w: float, duration_h: float) -> float:
    """Return the surplus factor ``available / required``.

    A value of 1.30 means exactly the 30 % target; 1.53 means 53 % surplus.
    Raises :class:`EnergyError` for zero load or zero duration instead of
    dividing by zero, so a bad row is reported rather than shown as infinity.
    """
    energy = _number("pack_wh", pack_wh, minimum=0.0)
    load = _number("load_w", load_w, minimum=0.0)
    hours = _number("duration_h", duration_h, minimum=0.0)
    if load <= 0.0:
        raise EnergyError(
            "load_w is 0 W: margin is undefined (no division by zero)"
        )
    if hours <= 0.0:
        raise EnergyError(
            "duration_h is 0 h: margin is undefined (no division by zero)"
        )
    required = load * hours
    if required <= 0.0:
        raise EnergyError("required energy is 0 Wh: margin is undefined")
    return energy / required


def propagate(power_w: float, pct: float) -> tuple[float, float]:
    """Return the ``(low, high)`` power interval for ``power_w +/- pct``."""
    power = _number("power_w", power_w, minimum=0.0)
    percent = _number("pct", pct, minimum=0.0, maximum=100.0)
    delta = power * percent / 100.0
    return power - delta, power + delta


def correction_note() -> str:
    """Short reminder of the CAM4G Wh mistake, for the generated report.

    The phrase "bài học CAM4G" is intentional: the old project quoted a
    10 Ah pack as 37 Wh, which is the 3.7 V Li-ion figure.  LFP 1S is 3.2 V,
    so the nominal energy is 32 Wh and the 85 % usable figure is 27.2 Wh.
    """
    return (
        "10 Ah LFP ở 3.2 V là 32 Wh danh định, không phải 37 Wh. "
        "Con số 37 Wh là bài học CAM4G: nó ứng với 3.7 V của Li-ion, "
        "không dùng được cho LFP 1S. Với 85 % dùng được: 27.2 Wh."
    )


def default_g0_scenarios(hours: float = 7.0) -> list[Scenario]:
    """The three CAM4G-derived scenarios from docs/02 section 3.

    All are estimates: there is no measured power figure yet, so ``measured``
    is False and the report must say G0 has not been passed.
    """
    duration_h = _number("hours", hours, minimum=0.0)
    if duration_h <= 0.0:
        raise EnergyError(f"hours must be > 0, got {hours!r}")
    duration_s = duration_h * 3600.0
    return [
        Scenario("Ghi cục bộ", "S2", 1.4, duration_s, 0.0, False),
        Scenario("Ghi + live 720p", "S3", 2.3, duration_s, 0.0, False),
        Scenario("Đêm: IR + live 720p", "S3+IR", 3.8, duration_s, 0.0, False),
    ]
