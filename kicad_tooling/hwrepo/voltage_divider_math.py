"""Shared nominal voltage-divider calculations for mapped circuit checks."""

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
