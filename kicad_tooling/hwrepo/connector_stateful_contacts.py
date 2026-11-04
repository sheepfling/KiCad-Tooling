"""Check source-mapped stateful connector contacts against native net assignments."""

from __future__ import annotations

from .connector_stateful_contact_models import (
    ConnectorStatefulContactMap,
)
from .design_lint_connector_stateful_contact_candidate_evidence import (
    RULE_ID as _RULE_ID,
)
from .design_lint_connector_stateful_contact_candidate_evidence import (
    StatefulConnectorContactCandidate,
    StatefulContactMapMismatchEvidence,
    StatefulContactTopologyEvidence,
    stateful_contact_identity_issues,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID = _RULE_ID


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
        identity_issues = stateful_contact_identity_issues(requirement, observed)
        if identity_issues:
            findings.append(
                StatefulConnectorContactCandidate.from_source_evidence(
                    StatefulContactMapMismatchEvidence(
                        observed=observed,
                        contact_map=contact_map,
                        requirement=requirement,
                        identity_issues=identity_issues,
                    ),
                    subject=(
                        f"{requirement.reference}: stateful contact map no longer matches source"
                    ),
                    message=(
                        "The project-authored connector contact map does not match the current "
                        "native component identity or complete pin inventory. Review the exact "
                        "part source and refresh or retire the map before relying on this check."
                    ),
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
                StatefulConnectorContactCandidate.from_source_evidence(
                    StatefulContactTopologyEvidence(
                        observed=observed,
                        contact_map=contact_map,
                        requirement=requirement,
                        pair=pair,
                        first_nets=first_nets,
                        second_nets=second_nets,
                        topology_state=state,
                    ),
                    subject=f"{requirement.reference}: mapped switch contacts {pair.id} {state}",
                    message=(
                        "The reviewed physical contact pair changes state when a plug is "
                        f"{'inserted' if pair.closed_when == 'plug_removed' else 'removed'}, but "
                        "the native schematic does not give both contact terminals distinct, "
                        "unambiguous nets. Review the exact connector pinout and schematic "
                        "wiring. This check does not infer the contact state from a symbol name."
                    ),
                )
            )
    return tuple(findings)
