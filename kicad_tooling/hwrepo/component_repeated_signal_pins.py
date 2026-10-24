"""Review repeated signal functions assigned to separate component nets."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_identity import (
    connector_candidate_references,
    is_named_supply_function,
    is_return_function,
    is_shield_function,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "component.repeated_signal_pin_assignment_divergence"
UNASSIGNED_RULE_ID: DesignLintRuleId = "component.repeated_signal_pin_unassigned"
_SIGNAL_ELECTRICAL_TYPES = frozenset(
    {"input", "output", "bidirectional", "tri_state", "open_collector", "open_emitter"}
)


@dataclass(frozen=True)
class _SignalPin:
    pin: str
    function: str
    assignments: tuple[str, ...]


@dataclass(frozen=True)
class _RepeatedSignalPinGroup:
    reference: str
    symbol: str
    function: str
    electrical_type: str
    pins: tuple[_SignalPin, ...]


def _repeated_signal_pin_groups(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[_RepeatedSignalPinGroup, ...]:
    """Group exact repeated signal functions with complete native pin evidence."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    fitted_references = {reference.casefold() for reference in observed.components}
    references_by_key = {reference.casefold(): reference for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    declared_pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions_by_component: dict[str, list[tuple[str, str]]] = {}
    types_by_pin = {pin.casefold(): value for pin, value in observed.pin_electrical_types.items()}
    for pin, function in observed.pin_functions.items():
        if "." not in pin:
            continue
        reference, number = pin.rsplit(".", 1)
        reference_key = reference.casefold()
        functions_by_component.setdefault(reference_key, []).append((number.casefold(), function))

    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    groups: list[_RepeatedSignalPinGroup] = []
    for reference_key, pin_functions in functions_by_component.items():
        if (
            reference_key not in fitted_references
            or reference_key in connector_references
            or reference_key in dnp_references
            or reference_key not in symbols
        ):
            continue
        inventory = declared_pin_numbers.get(reference_key)
        pin_numbers = {number for number, _ in pin_functions}
        if inventory is None or len(pin_functions) != len(inventory) or pin_numbers != inventory:
            continue

        grouped: dict[tuple[str, str], list[_SignalPin]] = {}
        for number, function in pin_functions:
            if (
                pin_function_is_generic(function)
                or is_named_supply_function(function)
                or is_return_function(function)
                or is_shield_function(function)
            ):
                continue
            pin = f"{references_by_key[reference_key]}.{number}"
            electrical_type = types_by_pin.get(pin.casefold())
            if electrical_type is None:
                continue
            normalized_type = electrical_type.strip().casefold().replace("-", "_")
            if normalized_type not in _SIGNAL_ELECTRICAL_TYPES:
                continue
            normalized_function = " ".join(function.casefold().split())
            assignments = tuple(
                sorted(
                    nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item)
                )
            )
            grouped.setdefault((normalized_function, normalized_type), []).append(
                _SignalPin(pin=pin, function=function, assignments=assignments)
            )

        for (_, normalized_type), entries in grouped.items():
            if len(entries) < 2:
                continue
            pins = tuple(sorted(entries, key=lambda item: (item.pin.casefold(), item.pin)))
            groups.append(
                _RepeatedSignalPinGroup(
                    reference=pins[0].pin.rsplit(".", 1)[0],
                    symbol=symbols[reference_key],
                    function=pins[0].function,
                    electrical_type=normalized_type,
                    pins=pins,
                )
            )
    return tuple(
        sorted(
            groups,
            key=lambda item: (
                item.reference.casefold(),
                item.function.casefold(),
                item.electrical_type,
            ),
        )
    )


def _group_evidence(group: _RepeatedSignalPinGroup) -> dict[str, tuple[str, ...]]:
    evidence = {pin.pin: pin.assignments for pin in group.pins}
    evidence["component_symbol"] = (group.symbol,)
    evidence["pin_function"] = (group.function,)
    evidence["electrical_type"] = (group.electrical_type,)
    return evidence


def component_signal_pin_net_divergences(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Find fitted non-connectors with identical signal pins assigned to different nets.

    This exact-function prompt is deliberately conservative: only complete
    pin inventories, explicit signal functions, recognized signal electrical
    types, and unique assignments participate. It does not infer that the
    pins should be tied.
    """
    candidates: list[Candidate] = []
    for group in _repeated_signal_pin_groups(observed, declared_connector_references):
        if any(len(pin.assignments) != 1 for pin in group.pins):
            continue
        if len({pin.assignments[0].casefold() for pin in group.pins}) < 2:
            continue
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{group.reference} ({group.symbol}): repeated {group.function} signal pins "
                    "use separate nets"
                ),
                message=(
                    "Multiple fitted signal pins on this component share the same explicit "
                    "native function and electrical type but use different schematic nets. "
                    "Review whether these are separate channels or whether a connection was "
                    "missed. This prompt does not require the pins to be tied."
                ),
                evidence=_group_evidence(group),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))


def component_repeated_signal_pin_unassigned(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review repeated explicit signal-function groups with both open and assigned pins."""
    candidates: list[Candidate] = []
    for group in _repeated_signal_pin_groups(observed, declared_connector_references):
        if any(len(pin.assignments) > 1 for pin in group.pins):
            continue
        assigned = tuple(pin.pin for pin in group.pins if pin.assignments)
        unassigned = tuple(pin.pin for pin in group.pins if not pin.assignments)
        if not assigned or not unassigned:
            continue
        evidence = _group_evidence(group)
        evidence["assigned_signal_pins"] = assigned
        evidence["unassigned_signal_pins"] = unassigned
        candidates.append(
            Candidate(
                rule_id=UNASSIGNED_RULE_ID,
                subject=(
                    f"{group.reference} ({group.symbol}): repeated {group.function} signal pins "
                    "include an unassigned pin"
                ),
                message=(
                    "At least one fitted pin with this explicit native signal function and "
                    "electrical type has no schematic net assignment while another matching pin "
                    "is assigned. Review whether the open member is intentionally unused or a "
                    "connection was missed. This prompt does not require the pins to be tied."
                ),
                evidence=evidence,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
