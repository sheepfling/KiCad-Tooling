"""Check source-mapped stateful connector contacts against native net assignments."""

from __future__ import annotations

from .connector_stateful_contact_models import (
    ConnectorStatefulContactMap,
    ConnectorStatefulContactRequirement,
)
from .design_lint_types import Candidate
from .models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID = "connector.stateful_contact_topology_mismatch"


def _identity_issues(
    requirement: ConnectorStatefulContactRequirement,
    observed: NetlistContract,
) -> tuple[str, ...]:
    reference_key = requirement.reference.casefold()
    components = {key.casefold(): value for key, value in observed.components.items()}
    symbols = {key.casefold(): value for key, value in observed.component_symbols.items()}
    inventories = {
        key.casefold(): {pin.casefold() for pin in values}
        for key, values in observed.component_pin_numbers.items()
    }
    component = components.get(reference_key)
    issues: list[str] = []
    if component is None:
        issues.append(f"{requirement.reference} is absent from the native netlist")
    else:
        if symbols.get(reference_key) != requirement.expected_symbol:
            issues.append(
                f"symbol is {symbols.get(reference_key) or 'unknown'}; "
                f"expected {requirement.expected_symbol}"
            )
        if component.value != requirement.expected_value:
            issues.append(f"value is {component.value}; expected {requirement.expected_value}")
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"footprint is {component.footprint or 'empty'}; "
                f"expected {requirement.expected_footprint}"
            )
        if component.part_id != requirement.expected_part_id:
            issues.append(
                f"PART_ID is {component.part_id or 'missing'}; "
                f"expected {requirement.expected_part_id}"
            )

    expected_pins = {pin.casefold() for pin in requirement.native_pin_numbers}
    actual_pins = inventories.get(reference_key)
    if actual_pins != expected_pins:
        issues.append(
            "native pin inventory is "
            f"{', '.join(sorted(actual_pins or ())) or 'unknown'}; "
            f"expected {', '.join(sorted(expected_pins))}"
        )
    return tuple(issues)


def stateful_connector_contact_findings(
    observed: NetlistContract,
    contact_map: ConnectorStatefulContactMap | None,
) -> tuple[Candidate, ...]:
    """Flag mapped state-dependent contacts that the schematic shorts or leaves open."""
    if contact_map is None:
        return ()

    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets = netlist_pin_net_index(observed)
    findings: list[Candidate] = []
    for requirement in sorted(contact_map.requirements, key=lambda item: item.reference.casefold()):
        if requirement.reference.casefold() in dnp:
            continue
        identity_issues = _identity_issues(requirement, observed)
        if identity_issues:
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(
                        f"{requirement.reference}: stateful contact map no longer matches source"
                    ),
                    message=(
                        "The project-authored connector contact map does not match the current "
                        "native component identity or complete pin inventory. Review the exact "
                        "part source and refresh or retire the map before relying on this check."
                    ),
                    evidence={
                        "requirement_id": (requirement.id,),
                        "reference": (requirement.reference,),
                        "identity_issues": identity_issues,
                        "map_basis": (contact_map.basis,),
                    },
                )
            )
            continue

        for pair in sorted(requirement.contact_pairs, key=lambda item: item.id.casefold()):
            first_pin = f"{requirement.reference}.{pair.first_pin}"
            second_pin = f"{requirement.reference}.{pair.second_pin}"
            first_nets = tuple(sorted(pin_nets.get(first_pin.casefold(), ())))
            second_nets = tuple(sorted(pin_nets.get(second_pin.casefold(), ())))
            if len(first_nets) == 1 and len(second_nets) == 1 and first_nets[0] != second_nets[0]:
                continue

            if not first_nets or not second_nets:
                state = "unassigned"
            elif len(first_nets) != 1 or len(second_nets) != 1:
                state = "ambiguous_assignment"
            else:
                state = "permanently_bypassed"
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=f"{requirement.reference}: mapped switch contacts {pair.id} {state}",
                    message=(
                        "The reviewed physical contact pair changes state when a plug is "
                        f"{'inserted' if pair.closed_when == 'plug_removed' else 'removed'}, but "
                        "the native schematic does not give both contact terminals distinct, "
                        "unambiguous nets. Review the exact connector pinout and schematic "
                        "wiring. This check does not infer the contact state from a symbol name."
                    ),
                    evidence={
                        "requirement_id": (requirement.id,),
                        "reference": (requirement.reference,),
                        "contact_pair": (pair.id,),
                        "first_pin": (first_pin,),
                        "second_pin": (second_pin,),
                        "first_nets": first_nets,
                        "second_nets": second_nets,
                        "closed_when": (pair.closed_when,),
                        "source_basis": (pair.source_basis,),
                        "map_basis": (contact_map.basis,),
                        "topology_state": (state,),
                    },
                )
            )
    return tuple(findings)
