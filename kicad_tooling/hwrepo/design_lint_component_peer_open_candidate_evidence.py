"""Source-bound evidence for generic component peer pins left open."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_scan import (
    GENERIC_COMPONENT_MIXED_PIN_TYPES,
    GENERIC_COMPONENT_PIN_TYPES,
    PeerPinAssignmentOutlier,
    PeerPinAssignmentScan,
    scan_component_peer_pin_assignments,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

ComponentPeerOpenRuleId = Literal[
    "component.generic_peer_pin_all_open",
    "component.generic_peer_pin_mixed_open",
]


@dataclass(frozen=True, slots=True)
class GenericComponentPeerOpenScanEvidence:
    """A generic open-peer scan rechecked against its exact netlist source."""

    observed: NetlistContract
    scan: PeerPinAssignmentScan
    declared_references: tuple[str, ...]
    rule_id: ComponentPeerOpenRuleId

    def __post_init__(self) -> None:
        current = _current_scan(self.observed, self.declared_references, self.rule_id)
        if self.scan != current:
            raise ValueError("Generic component peer scan must match its current netlist")

    @classmethod
    def from_scan(
        cls,
        *,
        observed: NetlistContract,
        scan: PeerPinAssignmentScan,
        declared_references: tuple[str, ...],
        rule_id: ComponentPeerOpenRuleId,
    ) -> GenericComponentPeerOpenScanEvidence:
        """Bind a rule-specific scan to the netlist and connector scope it used."""
        return cls(
            observed=observed,
            scan=scan,
            declared_references=declared_references,
            rule_id=rule_id,
        )

    def for_outlier(
        self,
        outlier: PeerPinAssignmentOutlier,
    ) -> GenericComponentPeerOpenEvidence:
        """Retain one current scan member as projectable typed evidence."""
        if outlier not in self.scan.outliers:
            raise ValueError("Generic component peer outlier must belong to its source scan")
        return GenericComponentPeerOpenEvidence(scan_evidence=self, outlier=outlier)


@dataclass(frozen=True, slots=True)
class GenericComponentPeerOpenEvidence:
    """One all-open or mixed-open component peer record from a validated scan."""

    scan_evidence: GenericComponentPeerOpenScanEvidence
    outlier: PeerPinAssignmentOutlier

    def __post_init__(self) -> None:
        if self.outlier not in self.scan_evidence.scan.outliers:
            raise ValueError("Generic component peer outlier must belong to its source scan")
        _validate_open_peer_outlier(self.scan_evidence.rule_id, self.outlier)


def _current_scan(
    observed: NetlistContract,
    declared_references: tuple[str, ...],
    rule_id: ComponentPeerOpenRuleId,
) -> PeerPinAssignmentScan:
    if rule_id == "component.generic_peer_pin_all_open":
        return scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=GENERIC_COMPONENT_PIN_TYPES,
            require_generic_pin_functions=True,
            assignment_pattern="all_open",
            require_shared_anchor=True,
        )
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=GENERIC_COMPONENT_MIXED_PIN_TYPES,
        require_generic_pin_functions=True,
        require_shared_anchor=True,
        minimum_peer_count=3,
        minimum_assigned_peer_count=2,
        require_assigned_peers_on_same_net=True,
    )


def _validate_open_peer_outlier(
    rule_id: ComponentPeerOpenRuleId,
    outlier: PeerPinAssignmentOutlier,
) -> None:
    assignments = outlier.assignments
    open_pins = tuple(pin for pin, nets in assignments.items() if not nets)
    assigned_pins = tuple(pin for pin, nets in assignments.items() if nets)
    if not outlier.shared_anchor_contacts:
        raise ValueError("Generic component peer open evidence requires a shared anchor")
    if rule_id == "component.generic_peer_pin_all_open":
        if len(open_pins) < 2 or assigned_pins:
            raise ValueError("All-open component peer evidence requires every peer pin open")
        return

    assigned_nets = {assignments[pin] for pin in assigned_pins}
    if (
        len(assignments) < 3
        or not open_pins
        or len(assigned_pins) < 2
        or len(assigned_nets) != 1
        or len(next(iter(assigned_nets), ())) != 1
    ):
        raise ValueError("Mixed-open component peer evidence requires two peers on one net")


def project_generic_component_peer_open_evidence(
    source: GenericComponentPeerOpenEvidence,
) -> CandidateEvidenceProjection:
    """Project source-validated open-peer evidence to the established report fields."""
    _validate_open_peer_outlier(source.scan_evidence.rule_id, source.outlier)
    outlier = source.outlier
    identity = component_peer_pin_identity_context(outlier)
    evidence = dict(outlier.assignments)
    evidence.update(identity.evidence)
    evidence.update(
        {
            "pin_number": (outlier.pin_number,),
            "pin_function": (outlier.pin_function or "",),
            "pin_electrical_type": (outlier.electrical_type,),
        }
    )
    open_pins = tuple(pin for pin, nets in outlier.assignments.items() if not nets)
    if source.scan_evidence.rule_id == "component.generic_peer_pin_all_open":
        evidence["unassigned_pins"] = open_pins
        evidence["shared_anchor_contacts"] = outlier.shared_anchor_contacts
    else:
        assigned_pins = tuple(pin for pin, nets in outlier.assignments.items() if nets)
        assigned_net = next(iter({outlier.assignments[pin] for pin in assigned_pins}))
        evidence.update(
            {
                "assigned_pins": assigned_pins,
                "unassigned_pins": open_pins,
                "shared_assignment_net": assigned_net,
            }
        )
        evidence["shared_anchor_contacts"] = outlier.shared_anchor_contacts
    return CandidateEvidenceProjection(
        rule_id=source.scan_evidence.rule_id,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class GenericComponentPeerOpenCandidate(Candidate):
    """Finding that keeps the current observation and peer scan behind its fields."""

    source_evidence: GenericComponentPeerOpenEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: GenericComponentPeerOpenEvidence,
        *,
        subject: str,
        message: str,
    ) -> GenericComponentPeerOpenCandidate:
        projection = project_generic_component_peer_open_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_generic_component_peer_open_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Generic component peer open fields must match their source")
