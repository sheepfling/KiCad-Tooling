"""Validate exact source-mapped two-pin reference-bond components."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from .models import NetlistContract, ReferenceBondRequirement

_Value = TypeVar("_Value")


def _lookup(mapping: Mapping[str, _Value], reference: str) -> _Value | None:
    matches = [
        value
        for candidate, value in mapping.items()
        if candidate.casefold() == reference.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def reference_bond_issues(
    observed: NetlistContract, requirement: ReferenceBondRequirement
) -> tuple[str, ...]:
    """Compare one reviewed passive bond and its exact pins, value, and nets."""
    issues: list[str] = []
    reference = requirement.reference
    component = _lookup(observed.components, reference)
    if component is None:
        return (f"{reference} is absent or ambiguous in the native netlist",)
    if component.value != requirement.expected_value:
        issues.append(
            f"{reference} value is {component.value or '<empty>'}; expected {requirement.expected_value}"
        )
    if component.footprint != requirement.expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {requirement.expected_footprint}"
        )
    symbol = _lookup(observed.component_symbols, reference)
    if symbol != requirement.expected_symbol:
        issues.append(
            f"{reference} symbol is {symbol or '<unknown>'}; expected {requirement.expected_symbol}"
        )
    if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{reference} is marked DNP but the mapped reference bond requires it fitted")

    expected_pins = {requirement.side_a_pin.casefold(), requirement.side_b_pin.casefold()}
    inventory = _lookup(observed.component_pin_numbers, reference)
    if inventory is None:
        issues.append(f"{reference} native pin inventory is unavailable")
    else:
        actual_pins = {f"{reference}.{number}".casefold() for number in inventory}
        if actual_pins != expected_pins or len(inventory) != 2:
            issues.append(
                f"{reference} native pin inventory does not match the mapped two-pin bond"
            )

    electrical_types = {
        key.casefold(): value.casefold() for key, value in observed.pin_electrical_types.items()
    }
    for pin in (requirement.side_a_pin, requirement.side_b_pin):
        if electrical_types.get(pin.casefold()) != "passive":
            issues.append(f"{pin} is not exported as a passive bond pin")
    expected_assignments = (
        (requirement.side_a_pin, requirement.side_a_net),
        (requirement.side_b_pin, requirement.side_b_net),
    )
    for pin, expected_net in expected_assignments:
        assigned_nets = tuple(
            sorted(
                net
                for net, pins in observed.nets.items()
                if any(candidate.casefold() == pin.casefold() for candidate in pins)
            )
        )
        if assigned_nets != (expected_net,):
            issues.append(
                f"{pin} is on {', '.join(assigned_nets) or 'unconnected'}; expected {expected_net}"
            )
    return tuple(issues)
