"""Shared exact identity and pin-inventory checks for mapped regulator parts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract


class _MappedPin(Protocol):
    @property
    def pin(self) -> str: ...


class _MappedComponent(Protocol):
    reference: str
    value: str
    symbol: str
    footprint: str
    part_id: str | None

    @property
    def pins(self) -> Sequence[_MappedPin]: ...


def regulator_component_identity_issues(
    requirement: _MappedComponent,
    observed: NetlistContract,
) -> tuple[str, ...]:
    """Return identity, fitted-state, and complete-pin-inventory mismatches."""
    issues: list[str] = []
    component = lookup_unique_casefold(observed.components, requirement.reference)
    symbol = lookup_unique_casefold(observed.component_symbols, requirement.reference)
    if component is None:
        issues.append(f"{requirement.reference} is absent or ambiguous in the native netlist")
    else:
        if component.value != requirement.value:
            issues.append(
                f"{requirement.reference} value is {component.value!r}; expected {requirement.value!r}"
            )
        if component.footprint != requirement.footprint:
            issues.append(
                f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {requirement.footprint!r}"
            )
        if requirement.part_id is not None and (
            component.part_id is None
            or component.part_id.casefold() != requirement.part_id.casefold()
        ):
            issues.append(
                f"{requirement.reference} PART_ID is {component.part_id or '<missing>'}; "
                f"expected {requirement.part_id!r}"
            )
    if symbol != requirement.symbol:
        issues.append(
            f"{requirement.reference} symbol is {symbol or '<unknown>'}; "
            f"expected {requirement.symbol!r}"
        )
    if requirement.reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{requirement.reference} is marked DNP but the map requires it fitted")

    actual_pins = lookup_unique_casefold(observed.component_pin_numbers, requirement.reference)
    expected_numbers = {item.pin.rsplit(".", 1)[1].casefold() for item in requirement.pins}
    if actual_pins is None:
        issues.append(f"{requirement.reference} native pin inventory is unavailable or ambiguous")
    elif {str(item).casefold() for item in actual_pins} != expected_numbers:
        issues.append(
            f"{requirement.reference} native pin inventory differs from the complete authored map"
        )
    return tuple(issues)
