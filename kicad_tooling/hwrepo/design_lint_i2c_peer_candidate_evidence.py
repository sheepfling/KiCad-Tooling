"""Typed source projections for I2C shared-bus reference reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import CandidateEvidenceProjection
from .i2c_peer_reference_scan import I2cPeerReferenceReview, I2cPeerReferenceScan
from .peer_reference_candidate_keys import (
    I2cPeerBusKey,
    PeerReferenceCandidate,
    project_peer_reference_identity,
)


@dataclass(frozen=True, slots=True)
class I2cPeerReferenceFindingEvidence:
    """One I2C reference review and the scan that produced its endpoints."""

    scan: I2cPeerReferenceScan
    review: I2cPeerReferenceReview

    def __post_init__(self) -> None:
        if self.review not in self.scan.reviews:
            raise ValueError("I2C peer review must belong to its source scan")


_I2C_PEER_REFERENCE: DesignLintRuleId = "bus.i2c_peer_reference_review"


def project_i2c_peer_reference_evidence(
    source: I2cPeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project an exact I2C bus review into its established report fields."""
    bus = source.review
    endpoints = bus.endpoints
    identity = project_peer_reference_identity(I2cPeerBusKey(bus.sda_net, bus.scl_net))
    assignments = tuple(
        f"{item.reference}: {item.sda_pin} on {item.sda_net}; "
        f"{item.scl_pin} on {item.scl_net}; "
        + (
            f"{', '.join(pin.pin for pin in item.reference_pins)} on {item.reference_net}"
            if item.reference_net is not None
            else "reference assignment incomplete"
        )
        for item in endpoints
    )
    evidence = {
        **identity.evidence,
        "participants": tuple(item.reference for item in endpoints),
        "signal_pins": tuple(pin for item in endpoints for pin in (item.sda_pin, item.scl_pin)),
        "reference_assignments": assignments,
    }
    if bus.incomplete_references:
        evidence["incomplete_reference_evidence"] = bus.incomplete_references
    return CandidateEvidenceProjection(rule_id=_I2C_PEER_REFERENCE, evidence=evidence)


@dataclass(frozen=True, slots=True)
class I2cPeerReferenceCandidate(PeerReferenceCandidate):
    """I2C peer candidate retaining its scan, review, and SDA/SCL identity."""

    source_evidence: I2cPeerReferenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I2cPeerReferenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> I2cPeerReferenceCandidate:
        projection = project_i2c_peer_reference_evidence(source_evidence)
        review = source_evidence.review
        identity = I2cPeerBusKey(review.sda_net, review.scl_net)
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
        projection = project_i2c_peer_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I2C peer fields must match their typed source projection")
