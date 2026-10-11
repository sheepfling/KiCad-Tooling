"""Check exact project-authored USB paths through multi-pin components."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar

from .models import ComponentContract, NetlistContract
from .usb_data_path_models import UsbDataPathInlineComponentRequirement

_Value = TypeVar("_Value")


@dataclass(frozen=True)
class UsbInlineComponentCheck:
    component_issues: tuple[str, ...]
    positive_issues: tuple[str, ...]
    negative_issues: tuple[str, ...]


def _lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def check_usb_inline_component(
    requirement: UsbDataPathInlineComponentRequirement,
    observed: NetlistContract,
) -> UsbInlineComponentCheck:
    """Compare complete native component identity, pin inventory, and pin disposition."""
    component_issues: list[str] = []
    positive_issues: list[str] = []
    negative_issues: list[str] = []

    component = _lookup(observed.components, requirement.reference)
    if not isinstance(component, ComponentContract):
        component_issues.append(
            f"{requirement.reference} is absent or ambiguous in the native netlist"
        )
    else:
        if component.footprint != requirement.expected_footprint:
            component_issues.append(
                f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {requirement.expected_footprint}"
            )

    symbol = _lookup(observed.component_symbols, requirement.reference)
    if symbol != requirement.expected_symbol:
        component_issues.append(
            f"{requirement.reference} symbol is {symbol or '<unknown>'}; "
            f"expected {requirement.expected_symbol}"
        )
    if requirement.reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        component_issues.append(f"{requirement.reference} is marked DNP")

    pin_numbers = _lookup(observed.component_pin_numbers, requirement.reference)
    expected_numbers = {item.pin.rsplit(".", 1)[1].casefold() for item in requirement.pins}
    if pin_numbers is None:
        component_issues.append(f"{requirement.reference} native pin inventory is unavailable")
    else:
        actual_numbers = {number.casefold() for number in pin_numbers}
        if len(actual_numbers) != len(pin_numbers) or actual_numbers != expected_numbers:
            missing = sorted(expected_numbers - actual_numbers)
            extra = sorted(actual_numbers - expected_numbers)
            details: list[str] = []
            if missing:
                details.append(f"missing {', '.join(missing)}")
            if extra:
                details.append(f"unexpected {', '.join(extra)}")
            if len(actual_numbers) != len(pin_numbers):
                details.append("duplicate native pin numbers")
            component_issues.append(
                f"{requirement.reference} native pin inventory differs from the exact map "
                f"({'; '.join(details) or 'unknown difference'})"
            )

    data_pin_lines = {
        requirement.positive_connector_pin.casefold(): positive_issues,
        requirement.positive_phy_pin.casefold(): positive_issues,
        requirement.negative_connector_pin.casefold(): negative_issues,
        requirement.negative_phy_pin.casefold(): negative_issues,
    }
    assigned_by_pin: dict[str, set[str]] = {}
    unconnected_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assigned_by_pin.setdefault(pin.casefold(), set()).add(net)
    for net, pins in observed.unconnected_nets.items():
        for pin in pins:
            unconnected_by_pin.setdefault(pin.casefold(), set()).add(net)

    for item in sorted(requirement.pins, key=lambda pin: (pin.pin.casefold(), pin.pin)):
        pin_key = item.pin.casefold()
        issues = data_pin_lines.get(pin_key, component_issues)
        actual_nets = assigned_by_pin.get(pin_key, set())
        unconnected_evidence = unconnected_by_pin.get(pin_key, set())
        if item.disposition == "net":
            expected_net = item.net or "<missing>"
            if (
                len(actual_nets) != 1
                or next(iter(actual_nets), "").casefold() != expected_net.casefold()
            ):
                actual = ", ".join(sorted(actual_nets, key=str.casefold)) or "unconnected"
                issues.append(f"{item.pin} is on {actual}; expected {expected_net}")
            if unconnected_evidence:
                issues.append(f"{item.pin} also has native unconnected-pin evidence")
        elif actual_nets or len(unconnected_evidence) != 1:
            actual = ", ".join(sorted(actual_nets, key=str.casefold)) or "no explicit no-connect"
            issues.append(f"{item.pin} is on {actual}; expected an explicit unconnected pin")

    return UsbInlineComponentCheck(
        component_issues=tuple(component_issues),
        positive_issues=tuple(positive_issues),
        negative_issues=tuple(negative_issues),
    )
