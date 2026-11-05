"""Shared voltage-divider calculations for mapped circuit checks."""

from __future__ import annotations

import math


def divider_tap_fraction(top_resistance_ohms: float, bottom_resistance_ohms: float) -> float:
    """Return Vtap/Vsource for a positive, unloaded two-resistor divider."""
    values = (top_resistance_ohms, bottom_resistance_ohms)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Divider resistances must be finite positive values")
    try:
        total = math.fsum(values)
    except OverflowError as exc:
        raise ValueError("Divider resistance sum exceeds the supported numeric range") from exc
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Divider resistance sum exceeds the supported numeric range")
    fraction = bottom_resistance_ohms / total
    if not math.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("Divider ratio exceeds the supported numeric range")
    return fraction


def divider_tolerance_voltage_range(
    source_minimum_v: float,
    source_maximum_v: float,
    top_resistance_ohms: float,
    bottom_resistance_ohms: float,
    top_tolerance_percent: float,
    bottom_tolerance_percent: float,
) -> tuple[float, float]:
    """Return the conservative output interval for bounded, independent resistor tolerance."""
    values = (
        source_minimum_v,
        source_maximum_v,
        top_resistance_ohms,
        bottom_resistance_ohms,
        top_tolerance_percent,
        bottom_tolerance_percent,
    )
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Divider voltage, resistance, and tolerance values must be finite")
    if source_minimum_v < 0 or source_maximum_v < source_minimum_v:
        raise ValueError("Divider source voltage range must be non-negative and ordered")
    if top_resistance_ohms <= 0 or bottom_resistance_ohms <= 0:
        raise ValueError("Divider resistances must be positive")
    if not 0 < top_tolerance_percent < 100 or not 0 < bottom_tolerance_percent < 100:
        raise ValueError("Divider resistor tolerances must be between 0% and 100%")

    top_tolerance = top_tolerance_percent / 100
    bottom_tolerance = bottom_tolerance_percent / 100
    top_minimum = top_resistance_ohms * (1 - top_tolerance)
    top_maximum = top_resistance_ohms * (1 + top_tolerance)
    bottom_minimum = bottom_resistance_ohms * (1 - bottom_tolerance)
    bottom_maximum = bottom_resistance_ohms * (1 + bottom_tolerance)
    minimum = source_minimum_v * divider_tap_fraction(top_maximum, bottom_minimum)
    maximum = source_maximum_v * divider_tap_fraction(top_minimum, bottom_maximum)
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        raise ValueError("Divider tolerance voltage range exceeds the supported numeric range")
    return minimum, maximum
