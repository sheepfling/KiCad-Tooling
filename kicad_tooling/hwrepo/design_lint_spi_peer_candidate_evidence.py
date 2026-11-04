"""Typed source projections for SPI shared-clock reference reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import CandidateEvidenceProjection
from .peer_reference_candidate_keys import (
    PeerReferenceCandidate,
    SpiPeerClockKey,
    project_peer_reference_identity,
)
from .spi_peer_reference_scan import SpiClockPeerBus, SpiPeerReferenceScan


@dataclass(frozen=True, slots=True)
class SpiPeerReferenceFindingEvidence:
    """One review bus bound to the scan that discovered it."""

    scan: SpiPeerReferenceScan
    review: SpiClockPeerBus

    def __post_init__(self) -> None:
        if not any(candidate is self.review for candidate in self.scan.reviews):
            raise ValueError("SPI peer review must belong to its source scan")


_SPI_PEER_REFERENCE: DesignLintRuleId = "bus.spi_peer_reference_review"


def project_spi_peer_reference_evidence(
    source: SpiPeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project an exact SPI reference review into its stable report fields."""
    bus = source.review
    endpoints = bus.endpoints
    identity = project_peer_reference_identity(SpiPeerClockKey(bus.clock_net))
    assignments = tuple(
        f"{item.reference}: {item.clock_pin} on {item.clock_net}; "
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
        "clock_pins": tuple(item.clock_pin for item in endpoints),
        "reference_assignments": assignments,
    }
    if bus.incomplete_references:
        evidence["incomplete_reference_evidence"] = bus.incomplete_references
    return CandidateEvidenceProjection(rule_id=_SPI_PEER_REFERENCE, evidence=evidence)


@dataclass(frozen=True, slots=True)
class SpiPeerReferenceCandidate(PeerReferenceCandidate):
    """SPI peer candidate retaining its scan, review, and canonical identity."""

    source_evidence: SpiPeerReferenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SpiPeerReferenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SpiPeerReferenceCandidate:
        projection = project_spi_peer_reference_evidence(source_evidence)
        identity = SpiPeerClockKey(source_evidence.review.clock_net)
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
        projection = project_spi_peer_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI peer fields must match their typed source projection")
