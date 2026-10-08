"""Project-authored power-path comparisons against native netlist evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar

from .models import NetlistContract, PowerPathMap, PowerPathRequirement

_Value = TypeVar("_Value")


@dataclass(frozen=True)
class PowerPathMismatch:
    path_id: str
    basis: str
    start_pin: str
    start_net: str
    end_pin: str
    end_net: str
    elements: tuple[str, ...]
    issues: tuple[str, ...]


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _pin_nets(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            net
            for net, pins in observed.nets.items()
            if any(candidate.casefold() == pin.casefold() for candidate in pins)
        )
    )


def _component_issues(
    observed: NetlistContract,
    reference: str,
    expected_symbol: str,
    expected_footprint: str,
    pins: tuple[tuple[str, str], ...],
    expected_pin_count: int | None = None,
) -> list[str]:
    issues: list[str] = []
    component = _lookup(observed.components, reference)
    if component is None:
        issues.append(f"{reference} is absent or ambiguous in the native netlist")
    elif component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint or '<empty>'}; "
            f"expected {expected_footprint}"
        )

    symbol = _lookup(observed.component_symbols, reference)
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol or '<unknown>'}; expected {expected_symbol}")
    if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{reference} is marked DNP but the mapped path requires it fitted")

    pin_numbers = _lookup(observed.component_pin_numbers, reference)
    if pin_numbers is None:
        issues.append(f"{reference} native pin inventory is unavailable or ambiguous")
    else:
        if expected_pin_count is not None and len(pin_numbers) != expected_pin_count:
            issues.append(
                f"{reference} has {len(pin_numbers)} native pins; "
                f"expected {expected_pin_count} for a mapped two-terminal element"
            )
        actual_numbers = {str(number).casefold() for number in pin_numbers}
        for pin, expected_net in pins:
            number = pin.rsplit(".", 1)[1]
            if number.casefold() not in actual_numbers:
                issues.append(f"{pin} is absent from the native pin inventory")
                continue
            actual_nets = _pin_nets(observed, pin)
            if actual_nets != (expected_net,):
                assigned = ", ".join(actual_nets) if actual_nets else "unconnected"
                issues.append(f"{pin} is assigned to {assigned}; expected {expected_net}")
    return issues


def _path_issues(path: PowerPathRequirement, observed: NetlistContract) -> tuple[str, ...]:
    issues: list[str] = []
    for endpoint in (path.start, path.end):
        issues.extend(
            _component_issues(
                observed,
                endpoint.reference,
                endpoint.symbol,
                endpoint.footprint,
                ((endpoint.pin, endpoint.net),),
            )
        )
    for element in path.elements:
        issues.extend(
            _component_issues(
                observed,
                element.reference,
                element.symbol,
                element.footprint,
                (
                    (element.side_a_pin, element.side_a_net),
                    (element.side_b_pin, element.side_b_net),
                ),
                expected_pin_count=2,
            )
        )
    return tuple(issues)


def power_path_mismatches(
    path_map: PowerPathMap, observed: NetlistContract
) -> tuple[PowerPathMismatch, ...]:
    """Compare exact authored path identities and pin/net assignments with a netlist."""
    mismatches: list[PowerPathMismatch] = []
    for path in path_map.paths:
        issues = _path_issues(path, observed)
        if not issues:
            continue
        mismatches.append(
            PowerPathMismatch(
                path_id=path.id,
                basis=path.basis,
                start_pin=path.start.pin,
                start_net=path.start.net,
                end_pin=path.end.pin,
                end_net=path.end.net,
                elements=tuple(
                    f"{item.reference} ({item.side_a_pin}@{item.side_a_net} → "
                    f"{item.side_b_pin}@{item.side_b_net})"
                    for item in path.elements
                ),
                issues=issues,
            )
        )
    return tuple(mismatches)
