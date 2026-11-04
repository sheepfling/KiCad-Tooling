"""Typed source records and projections for named connector power aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_peer_named_power_aliases import (
    ConnectorNamedPowerAliasPeer,
    ConnectorPowerElectricalType,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorNamedPowerAliasRuleId: TypeAlias = Literal[
    "connector.peer_power_input_open_assignment",
    "connector.peer_power_input_named_all_open",
    "connector.peer_power_input_named_assignment_divergence",
    "connector.peer_power_output_open_assignment",
    "connector.peer_power_output_named_all_open",
    "connector.peer_power_output_named_assignment_divergence",
]
ConnectorNamedPowerAliasFindingKind: TypeAlias = Literal[
    "mixed_open",
    "all_open",
    "divergent",
]

_RULE_SCOPE: dict[
    ConnectorNamedPowerAliasRuleId,
    tuple[ConnectorPowerElectricalType, ConnectorNamedPowerAliasFindingKind],
] = {
    "connector.peer_power_input_open_assignment": ("power_in", "mixed_open"),
    "connector.peer_power_input_named_all_open": ("power_in", "all_open"),
    "connector.peer_power_input_named_assignment_divergence": ("power_in", "divergent"),
    "connector.peer_power_output_open_assignment": ("power_out", "mixed_open"),
    "connector.peer_power_output_named_all_open": ("power_out", "all_open"),
    "connector.peer_power_output_named_assignment_divergence": ("power_out", "divergent"),
}


def _finding_details(
    peer: ConnectorNamedPowerAliasPeer,
    rule_id: ConnectorNamedPowerAliasRuleId,
) -> tuple[
    ConnectorNamedPowerAliasFindingKind,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    electrical_type, finding_kind = _RULE_SCOPE[rule_id]
    group = peer.group
    if group.pin_electrical_type.strip().casefold() != electrical_type:
        raise ValueError("Named power alias rule must match the source pin electrical type")

    if finding_kind == "mixed_open":
        if any(len(nets) > 1 for nets in group.assignments.values()):
            raise ValueError("Mixed-open peer findings cannot include ambiguous assignments")
        assigned = tuple(pin for pin, nets in group.assignments.items() if len(nets) == 1)
        opened = tuple(pin for pin, nets in group.assignments.items() if not nets)
        if not assigned or not opened:
            raise ValueError("Mixed-open peer findings require assigned and open pins")
        return finding_kind, assigned, opened, ()

    if finding_kind == "all_open":
        if any(group.assignments.values()):
            raise ValueError("All-open peer findings cannot include assigned pins")
        return finding_kind, (), tuple(group.assignments), ()

    if any(len(nets) != 1 for nets in group.assignments.values()):
        raise ValueError("Divergent peer findings require one assignment per peer pin")
    distinct_nets = {nets[0] for nets in group.assignments.values()}
    if len(distinct_nets) < 2:
        raise ValueError("Divergent peer findings require multiple assigned nets")
    assignments = tuple(f"{pin}={nets[0]}" for pin, nets in sorted(group.assignments.items()))
    return finding_kind, (), (), assignments


@dataclass(frozen=True, slots=True)
class ConnectorNamedPowerAliasFindingEvidence:
    """One guarded PART_ID peer group and its typed assignment finding."""

    peer: ConnectorNamedPowerAliasPeer
    rule_id: ConnectorNamedPowerAliasRuleId
    finding_kind: ConnectorNamedPowerAliasFindingKind
    assigned_peer_pins: tuple[str, ...] = ()
    open_peer_pins: tuple[str, ...] = ()
    distinct_net_assignments: tuple[str, ...] = ()

    @classmethod
    def from_peer(
        cls,
        peer: ConnectorNamedPowerAliasPeer,
        rule_id: ConnectorNamedPowerAliasRuleId,
    ) -> ConnectorNamedPowerAliasFindingEvidence:
        finding_kind, assigned, opened, distinct = _finding_details(peer, rule_id)
        return cls(
            peer=peer,
            rule_id=rule_id,
            finding_kind=finding_kind,
            assigned_peer_pins=assigned,
            open_peer_pins=opened,
            distinct_net_assignments=distinct,
        )

    def __post_init__(self) -> None:
        expected = _finding_details(self.peer, self.rule_id)
        actual = (
            self.finding_kind,
            self.assigned_peer_pins,
            self.open_peer_pins,
            self.distinct_net_assignments,
        )
        if actual != expected:
            raise ValueError("Named power alias evidence must match its exact peer assignments")


def project_connector_named_power_alias_evidence(
    source: ConnectorNamedPowerAliasFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project peer identity and the selected assignment details to report fields."""
    group = source.peer.group
    evidence: dict[str, tuple[str, ...]] = dict(group.assignments)
    evidence.update(
        {
            "peer_identity_basis": ("part_id",),
            "peer_identity": (group.part_id,),
            "peer_symbols": source.peer.symbols,
            "pin_number": (group.pin_number,),
            "pin_function": (source.peer.function,),
            "pin_electrical_type": (group.pin_electrical_type,),
        }
    )
    if group.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (group.peer_assignment_group,)
        evidence["peer_assignment_basis"] = group.peer_assignment_basis
    if source.finding_kind == "mixed_open":
        evidence["assigned_peer_pins"] = source.assigned_peer_pins
        evidence["open_peer_pins"] = source.open_peer_pins
    elif source.finding_kind == "all_open":
        evidence["open_peer_pins"] = source.open_peer_pins
    else:
        evidence["distinct_net_assignments"] = source.distinct_net_assignments
    return CandidateEvidenceProjection(rule_id=source.rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorNamedPowerAliasCandidate(Candidate):
    """Candidate retaining the exact typed peer group and assignment finding."""

    source_evidence: ConnectorNamedPowerAliasFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorNamedPowerAliasFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorNamedPowerAliasCandidate:
        projection = project_connector_named_power_alias_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_named_power_alias_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named power alias fields must match their typed source projection")


def connector_named_power_alias_candidate(
    peer: ConnectorNamedPowerAliasPeer,
    rule_id: ConnectorNamedPowerAliasRuleId,
    *,
    subject: str,
    message: str,
) -> ConnectorNamedPowerAliasCandidate:
    """Build a candidate for one already-selected named power alias predicate result."""
    source_evidence = ConnectorNamedPowerAliasFindingEvidence.from_peer(peer, rule_id)
    return ConnectorNamedPowerAliasCandidate.from_source_evidence(
        source_evidence,
        subject=subject,
        message=message,
    )
