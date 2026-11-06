"""Shared completeness checks for native connector pin metadata."""

from __future__ import annotations

from collections.abc import Mapping


def connector_pin_metadata_matches_inventory(
    reference: str,
    pin_numbers: tuple[str, ...],
    pin_functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
) -> bool:
    """Require exact function and electrical-type coverage for an inventory."""
    reference_key = reference.casefold()
    expected = {number.casefold() for number in pin_numbers}
    for metadata in (pin_functions, electrical_types):
        actual = {
            pin.rsplit(".", 1)[1].casefold()
            for pin in metadata
            if pin.rpartition(".")[0].casefold() == reference_key
        }
        if actual != expected:
            return False
    return all(
        pin_functions.get(f"{reference_key}.{number.casefold()}")
        and electrical_types.get(f"{reference_key}.{number.casefold()}")
        for number in pin_numbers
    )
