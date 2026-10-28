"""Diagnostics for native component-peer pin metadata comparisons."""

from __future__ import annotations

from collections.abc import Mapping

from .hwrepo.models import NetlistContract


def native_peer_metadata_mismatches(
    observed: NetlistContract,
    *,
    expected_symbols: Mapping[str, str],
    references: tuple[str, ...],
    pin_1_function: str,
    pin_type: str,
    pin_function: str,
) -> tuple[str, ...]:
    """Describe missing or changed native symbol and pin evidence."""
    expected_pin_numbers = {reference: ("1", "2") for reference in references}
    expected_pin_types = {
        f"{reference}.{number}": expected_type
        for reference in references
        for number, expected_type in (("1", "passive"), ("2", pin_type))
    }
    expected_pin_functions = {
        f"{reference}.{number}": expected_function
        for reference in references
        for number, expected_function in (("1", pin_1_function), ("2", pin_function))
    }
    checks = (
        ("component_symbols", observed.component_symbols, dict(expected_symbols)),
        (
            "component_pin_numbers",
            {reference: observed.component_pin_numbers.get(reference) for reference in references},
            expected_pin_numbers,
        ),
        (
            "pin_electrical_types",
            {pin: observed.pin_electrical_types.get(pin) for pin in expected_pin_types},
            expected_pin_types,
        ),
        (
            "pin_functions",
            {pin: observed.pin_functions.get(pin) for pin in expected_pin_functions},
            expected_pin_functions,
        ),
    )
    return tuple(
        f"{field}: expected {expected!r}, observed {actual!r}"
        for field, actual, expected in checks
        if actual != expected
    )
