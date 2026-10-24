"""Review fitted components whose recognized return pins span nets."""

from __future__ import annotations

from .connector_identity import connector_candidate_references, is_return_function
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "component.repeated_return_pin_function"


def component_return_pin_net_divergences(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
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

    candidates: list[Candidate] = []
    for entries in grouped.values():
        if len(entries) < 2 or any(len(assignments) != 1 for _, _, assignments in entries):
            continue
        if len({assignments[0].casefold() for _, _, assignments in entries}) < 2:
            continue
        entries.sort(key=lambda item: (item[0].casefold(), item[0]))
        reference = entries[0][0].rsplit(".", 1)[0]
        symbol = symbols[reference.casefold()]
        evidence = {pin: assignments for pin, _, assignments in entries}
        evidence["component_symbol"] = (symbol,)
        evidence["pin_functions"] = tuple(f"{pin}={function}" for pin, function, _ in entries)
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference} ({symbol}): return pins use distinct nets",
                message=(
                    "Multiple recognized ground or return pins on this fitted component use "
                    "different schematic nets. Review whether the split is intentional, such "
                    "as separate analog and digital domains, or whether a common or bonded "
                    "return relationship is missing. This prompt does not require those nets "
                    "to be joined."
                ),
                evidence=evidence,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
