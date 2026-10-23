"""Shared interpretation of KiCad pin electrical types for component checks."""

from __future__ import annotations

_OUTPUT_CAPABLE_PIN_TYPES = frozenset(
    {
        "output",
        "power_out",
        "bidirectional",
        "tri_state",
        "open_collector",
        "open_emitter",
    }
)


def is_output_capable_pin_type(pin_type: str) -> bool:
    """Return whether a native KiCad pin type can drive a connected component."""
    return pin_type.strip().casefold() in _OUTPUT_CAPABLE_PIN_TYPES
