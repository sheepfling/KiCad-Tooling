"""Typed source projections for CAN shared-pair reference reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .can_peer_reference_scan import CanPeerReferenceBus, CanPeerReferenceScan
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import CandidateEvidenceProjection
from .peer_reference_candidate_keys import (
    CanPeerBusKey,
    PeerReferenceCandidate,
    project_peer_reference_identity,
)


@dataclass(frozen=True, slots=True)
class CanPeerReferenceFindingEvidence:
    """One CAN bus review bound to its source scan."""

    scan: CanPeerReferenceScan
    review: CanPeerReferenceBus

    def __post_init__(self) -> None:
        if not any(candidate is self.review for candidate in self.scan.reviews):
            raise ValueError("CAN peer review must belong to its source scan")


_CAN_PEER_REFERENCE: DesignLintRuleId = "bus.can_peer_reference_review"


def project_can_peer_reference_evidence(
    source: CanPeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project an exact CAN reference review into the stable report fields."""
    bus = source.review
    endpoints = bus.endpoints
    identity = project_peer_reference_identity(CanPeerBusKey(bus.canh_net, bus.canl_net))
    evidence = {
        **identity.evidence,
        "participants": tuple(item.reference for item in endpoints),
        "line_assignments": tuple(
            f"{item.reference}: {item.canh_pin} on {item.canh_net}; "
            f"{item.canl_pin} on {item.canl_net}"
            for item in endpoints
        ),
        "reference_assignments": tuple(
            f"{item.reference}: "
            + (
                f"{', '.join(pin.pin for pin in item.reference_pins)} on {item.reference_net}"
                if item.reference_net is not None
                else "reference assignment incomplete"
            )
            for item in endpoints
        ),
    }
    if bus.incomplete_references:
        evidence["incomplete_reference_evidence"] = bus.incomplete_references
    return CandidateEvidenceProjection(rule_id=_CAN_PEER_REFERENCE, evidence=evidence)


@dataclass(frozen=True, slots=True)
class CanPeerReferenceCandidate(PeerReferenceCandidate):
    """CAN peer candidate retaining its scan, bus review, and line identity."""

    source_evidence: CanPeerReferenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanPeerReferenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> CanPeerReferenceCandidate:
        projection = project_can_peer_reference_evidence(source_evidence)
        bus = source_evidence.review
        identity = CanPeerBusKey(bus.canh_net, bus.canl_net)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            identity=identity,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        PeerReferenceCandidate.__post_init__(self)
        projection = project_can_peer_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("CAN peer-reference fields must match their typed source projection")
