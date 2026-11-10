"""Review split and open power-input contacts across unlike connector peers."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .connector_reviewed_peer_power_contacts import (
    ReviewedPeerPowerContactPair,
    reviewed_peer_power_contact_pairs,
    reviewed_peer_power_pair_evidence,
    sort_reviewed_peer_power_candidates,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_power_input_split"
PASSIVE_OPEN_RULE_ID: DesignLintRuleId = "connector.reviewed_peer_passive_power_input_open"
_POWER_INPUT_ELECTRICAL_TYPES = frozenset({"power_in", "passive"})


def reviewed_peer_power_input_split_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Find mapped power contacts split across unlike reviewed peers."""
    candidates: list[Candidate] = []
    pairs = reviewed_peer_power_contact_pairs(
        observed,
        coverage,
        electrical_types=_POWER_INPUT_ELECTRICAL_TYPES,
    )
    for pair in pairs:
        left, right = pair.pins
        if (
            len(left.nets) != 1
            or len(right.nets) != 1
            or left.nets[0].casefold() == right.nets[0].casefold()
        ):
            continue
        assignments = (
            f"{left.component_pin}={left.nets[0]}",
            f"{right.component_pin}={right.nets[0]}",
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                    f"{pair.classification} use separate nets"
                ),
                message=_finding_message(pair),
                evidence=reviewed_peer_power_pair_evidence(pair, assignments),
            )
        )
    return sort_reviewed_peer_power_candidates(candidates)


def reviewed_peer_passive_power_input_open_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review an open passive contact beside an assigned reviewed peer."""
    candidates: list[Candidate] = []
    pairs = reviewed_peer_power_contact_pairs(
        observed,
        coverage,
        electrical_types=_POWER_INPUT_ELECTRICAL_TYPES,
    )
    for pair in pairs:
        for opened_index, assigned_index in ((0, 1), (1, 0)):
            opened = pair.pins[opened_index]
            assigned = pair.pins[assigned_index]
            roles_are_eligible = (
                opened.role is None and assigned.role is None
                if pair.classification == "generic power inputs"
                else pair.classification in {"named power contacts", "mapped power contacts"}
                and opened.role == assigned.role == "supply"
            )
            if (
                pair.electrical_types[opened_index] != "passive"
                or not roles_are_eligible
                or opened.nets
                or opened.unconnected_reason is not None
                or len(assigned.nets) != 1
            ):
                continue
            assignments = (
                f"{opened.component_pin}=<unassigned>",
                f"{assigned.component_pin}={assigned.nets[0]}",
            )
            candidates.append(
                Candidate(
                    rule_id=PASSIVE_OPEN_RULE_ID,
                    subject=(
                        f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                        + (
                            "generic passive power-input contact is open beside its peer"
                            if pair.classification == "generic power inputs"
                            else "mapped passive power contact is open beside its peer"
                        )
                    ),
                    message=_passive_power_open_message(pair),
                    evidence=reviewed_peer_power_pair_evidence(pair, assignments),
                )
            )
    return sort_reviewed_peer_power_candidates(candidates)


def _passive_power_open_message(pair: ReviewedPeerPowerContactPair) -> str:
    """Explain why the mapped open is reviewable without making it a connection rule."""
    if pair.classification == "generic power inputs":
        return (
            "Unlike connector symbols in this source-reviewed peer group map generic contacts "
            "to the same interface signal and voltage domain, but one passive contact has no net "
            "while its peer has one assigned net. Review whether the open is intentional or a "
            "connection is missing. The map does not require tying the contacts, select a target "
            "net, or prove PCB copper continuity."
        )
    return (
        "Unlike connector symbols in this source-reviewed peer group map power contacts to the "
        "same interface signal and voltage domain, but one passive mapped supply contact has no "
        "net while its peer has one assigned net. Review whether the open is intentional or a "
        "connection is missing. The map does not require tying the contacts, select a target net, "
        "or prove PCB copper continuity."
    )


def _finding_message(pair: ReviewedPeerPowerContactPair) -> str:
    """Describe the evidence class without turning the map into a net requirement."""
    if pair.classification == "generic power inputs":
        contact = "generic native power contacts (power_in or passive)"
    elif pair.classification == "named power contacts":
        contact = "named native power contacts with different recognized supply functions"
    else:
        contact = "mapped power contacts with one generic and one named supply function"
    return (
        "Unlike connector symbols in this source-reviewed peer group map "
        f"{contact} to the same interface signal and voltage domain, but assign them to "
        "different nets. Review whether separate sources, filtering, or isolation are "
        "intentional. The map does not prove these nets should be joined or that PCB copper "
        "is continuous."
    )
