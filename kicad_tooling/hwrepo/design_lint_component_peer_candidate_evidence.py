"""Typed generic component-peer sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass

from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_scan import GENERIC_COMPONENT_PIN_TYPES, PeerPinAssignmentOutlier
from .design_lint_types import Candidate, CandidateEvidenceProjection


def project_generic_peer_pin_evidence(
    source: PeerPinAssignmentOutlier,
) -> CandidateEvidenceProjection:
    """Project one anchored strict-majority outlier to the established report fields."""
    if source.electrical_type.casefold() not in GENERIC_COMPONENT_PIN_TYPES:
        raise ValueError("Generic peer-pin evidence requires a generic electrical type")
    if source.majority_net is None or not source.outlier_pins or not source.shared_anchor_contacts:
        raise ValueError("Generic peer-pin evidence requires majority, outlier, and anchor data")

    identity = component_peer_pin_identity_context(source)
    return CandidateEvidenceProjection(
        rule_id="component.generic_peer_pin_assignment_outlier",
        evidence={
            **source.assignments,
            **identity.evidence,
            "pin_number": (source.pin_number,),
            "pin_function": (source.pin_function or "",),
            "pin_electrical_type": (source.electrical_type,),
            "majority_net": (source.majority_net,),
            "outlier_pins": source.outlier_pins,
            "shared_anchor_contacts": source.shared_anchor_contacts,
        },
    )


@dataclass(frozen=True, slots=True)
class GenericPeerPinCandidate(Candidate):
    """Internal generic peer finding retaining its immutable scan record."""

    source_evidence: PeerPinAssignmentOutlier

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PeerPinAssignmentOutlier,
        *,
        subject: str,
        message: str,
    ) -> GenericPeerPinCandidate:
        projection = project_generic_peer_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_generic_peer_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Generic peer candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Generic peer evidence must match its typed source projection")
