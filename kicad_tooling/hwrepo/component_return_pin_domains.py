"""Review fitted components whose recognized return pins span nets."""

from __future__ import annotations

from .connector_identity import connector_candidate_references, is_return_function
from .design_lint_component_return_candidate_evidence import (
    ComponentReturnPinCandidate,
    ComponentReturnPinFindingEvidence,
    ComponentReturnPinObservation,
    component_return_pin_candidate,
)
from .design_lint_rule_types import DesignLintRuleId
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "component.repeated_return_pin_function"


def component_return_pin_net_divergences(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[ComponentReturnPinCandidate, ...]:
    """Review a fitted non-connector with assigned return pins on distinct nets."""
    connectors = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    component_references = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    grouped: dict[str, list[tuple[str, str, tuple[str, ...]]]] = {}
    for pin, function in observed.pin_functions.items():
        if "." not in pin or not is_return_function(function):
            continue
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        if (
            reference_key not in component_references
            or reference_key in connectors
            or reference_key in unpopulated
            or reference_key not in symbols
        ):
            continue
        assignments = tuple(sorted(nets_by_pin.get(pin.casefold(), ()), key=str.casefold))
        grouped.setdefault(reference_key, []).append((pin, function, assignments))

    candidates: list[ComponentReturnPinCandidate] = []
    for entries in grouped.values():
        if len(entries) < 2 or any(len(assignments) != 1 for _, _, assignments in entries):
            continue
        if len({assignments[0].casefold() for _, _, assignments in entries}) < 2:
            continue
        entries.sort(key=lambda item: (item[0].casefold(), item[0]))
        reference = entries[0][0].rsplit(".", 1)[0]
        symbol = symbols[reference.casefold()]
        source = ComponentReturnPinFindingEvidence(
            observed=observed,
            declared_connector_references=declared_connector_references,
            reference=reference,
            symbol=symbol,
            pins=tuple(
                ComponentReturnPinObservation(pin, function, assignments)
                for pin, function, assignments in entries
            ),
        )
        candidates.append(component_return_pin_candidate(source))
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
