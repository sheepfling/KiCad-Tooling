"""Shared identity and pin-map checks for authored passive resistor arrays."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import NetlistContract
from .project_models import ComponentContract


@dataclass(frozen=True, slots=True)
class ResistorArrayNetlistEvidence:
    """Case-insensitive native evidence used by mapped resistor-array contracts."""

    components: Mapping[str, tuple[str, ComponentContract]]
    symbols: Mapping[str, str]
    pin_numbers: Mapping[str, frozenset[str]]
    dnp: frozenset[str]
    pin_nets: Mapping[str, frozenset[str]]

    @classmethod
    def from_netlist(cls, observed: NetlistContract) -> ResistorArrayNetlistEvidence:
        return cls(
            components={
                reference.casefold(): (reference, component)
                for reference, component in observed.components.items()
            },
            symbols={
                reference.casefold(): symbol
                for reference, symbol in observed.component_symbols.items()
            },
            pin_numbers={
                reference.casefold(): frozenset(number.casefold() for number in numbers)
                for reference, numbers in observed.component_pin_numbers.items()
            },
            dnp=frozenset(reference.casefold() for reference in observed.dnp_components),
            pin_nets=_pin_nets(observed),
        )


def resistor_array_component_issues(
    evidence: ResistorArrayNetlistEvidence,
    *,
    reference: str,
    expected_symbol: str,
    expected_footprint: str,
    expected_value: str,
    expected_part_id: str | None,
    channel_pins: tuple[tuple[str, str], ...],
    unmapped_pin_reasons: Mapping[str, str],
    component_kind: str = "mapped resistor array",
) -> tuple[str, ...]:
    """Check exact identity, fitted state, and complete symbol pin disposition."""
    key = reference.casefold()
    issues: list[str] = []
    entry = evidence.components.get(key)
    if entry is None:
        issues.append(f"{reference} is absent from the native netlist")
    else:
        _, component = entry
        if component.footprint != expected_footprint:
            issues.append(
                f"{reference} footprint is {component.footprint or 'empty'}; "
                f"expected {expected_footprint}"
            )
        if component.value.strip().casefold() != expected_value.strip().casefold():
            issues.append(f"{reference} value is {component.value}; expected {expected_value}")
        if expected_part_id is not None and component.part_id != expected_part_id:
            issues.append(
                f"{reference} PART_ID is {component.part_id or 'missing'}; "
                f"expected {expected_part_id}"
            )
    actual_symbol = evidence.symbols.get(key)
    if actual_symbol != expected_symbol:
        issues.append(
            f"{reference} symbol is {actual_symbol or 'unknown'}; expected {expected_symbol}"
        )
    if key in evidence.dnp:
        issues.append(f"{reference} is DNP but a {component_kind} is required")

    inventory = evidence.pin_numbers.get(key)
    if inventory is None:
        issues.append(f"{reference} has no native symbol pin inventory")
    else:
        expected_numbers = {
            pin.rsplit(".", 1)[1].casefold() for channel in channel_pins for pin in channel
        }
        expected_numbers.update(pin.rsplit(".", 1)[1].casefold() for pin in unmapped_pin_reasons)
        missing = tuple(sorted(expected_numbers - inventory))
        unreviewed = tuple(sorted(inventory - expected_numbers))
        if missing:
            issues.append(f"{reference} mapped pins are absent from symbol inventory: {missing}")
        if unreviewed:
            issues.append(
                f"{reference} has unreviewed symbol pins outside the array map: {unreviewed}"
            )
    return tuple(issues)


def resistor_array_channel_issue(
    evidence: ResistorArrayNetlistEvidence,
    *,
    reference: str,
    channel_id: str,
    pin_a: str,
    pin_b: str,
    net_a: str,
    net_b: str,
) -> str | None:
    """Require one native pin on each mapped net, allowing passive reversal."""
    assignments_a = evidence.pin_nets.get(pin_a.casefold(), frozenset())
    assignments_b = evidence.pin_nets.get(pin_b.casefold(), frozenset())
    direct = assignments_a == frozenset((net_a,)) and assignments_b == frozenset((net_b,))
    reversed_ends = assignments_a == frozenset((net_b,)) and assignments_b == frozenset((net_a,))
    if direct or reversed_ends:
        return None
    observed_a = ", ".join(sorted(assignments_a)) or "unconnected"
    observed_b = ", ".join(sorted(assignments_b)) or "unconnected"
    return (
        f"{reference} channel {channel_id}: {pin_a} is on {observed_a} and "
        f"{pin_b} is on {observed_b}; expected one pin on {net_a} and one on {net_b}"
    )


def _pin_nets(observed: NetlistContract) -> Mapping[str, frozenset[str]]:
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    return {pin: frozenset(nets) for pin, nets in pin_nets.items()}
