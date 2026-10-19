"""Project-authored power-path comparisons against native netlist evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .casefold_mapping_lookup import lookup_unique_casefold as _lookup
from .models import NetlistContract
from .power_path_models import PowerPathMap, PowerPathRequirement


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
    expected_part_id: str | None = None,
    expected_pin_function: str | None = None,
    expected_pin_electrical_type: str | None = None,
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
    if expected_part_id is not None:
        actual_part_id = None if component is None else component.part_id
        if actual_part_id is None or actual_part_id.casefold() != expected_part_id.casefold():
            issues.append(
                f"{reference} PART_ID is {actual_part_id or '<missing>'}; "
                f"expected {expected_part_id}"
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
    if expected_pin_function is not None:
        actual_function = _lookup(observed.pin_functions, pins[0][0])
        if (
            actual_function is None
            or actual_function.casefold() != expected_pin_function.casefold()
        ):
            issues.append(
                f"{pins[0][0]} native pin function is {actual_function or '<unknown>'}; "
                f"expected {expected_pin_function}"
            )
    if expected_pin_electrical_type is not None:
        actual_type = _lookup(observed.pin_electrical_types, pins[0][0])
        if actual_type is None or actual_type.casefold() != expected_pin_electrical_type.casefold():
            issues.append(
                f"{pins[0][0]} native electrical type is {actual_type or '<unknown>'}; "
                f"expected {expected_pin_electrical_type}"
            )
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
                expected_part_id=endpoint.part_id,
                expected_pin_function=endpoint.pin_function,
                expected_pin_electrical_type=endpoint.pin_electrical_type,
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
