"""Shared synthetic reference-pin role mutations for protocol lint tests."""

from __future__ import annotations

from collections.abc import Iterable

from kicad_tooling.hwrepo.models import NetlistContract


def with_unspecified_reference_pins(
    observed: NetlistContract,
    pins: Iterable[str],
    *,
    function: str = "VSS",
) -> NetlistContract:
    """Mark exact synthetic return pins as explicitly named, electrically unspecified."""
    selected = tuple(pins)
    return observed.model_copy(
        update={
            "pin_functions": {
                **observed.pin_functions,
                **{pin: function for pin in selected},
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                **{pin: "unspecified" for pin in selected},
            },
        }
    )
