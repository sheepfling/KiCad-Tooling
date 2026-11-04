"""Typed source projections for mapped RS-485 reference reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import CandidateEvidenceProjection
from .peer_reference_candidate_keys import (
    PeerReferenceCandidate,
    Rs485PeerPairKey,
    project_peer_reference_identity,
)
from .rs485_peer_reference_types import Rs485PeerReferencePair, Rs485PeerReferenceScan


@dataclass(frozen=True, slots=True)
class Rs485PeerReferenceFindingEvidence:
    """One mapped line-pair review and the authored-map scan that found it."""

    scan: Rs485PeerReferenceScan
    review: Rs485PeerReferencePair

    def __post_init__(self) -> None:
        if not any(candidate is self.review for candidate in self.scan.reviews):
            raise ValueError("RS-485 peer review must belong to its source scan")


_RS485_PEER_REFERENCE: DesignLintRuleId = "bus.rs485_peer_reference_review"


def project_rs485_peer_reference_evidence(
    source: Rs485PeerReferenceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project an exact mapped pair review into its existing report fields."""
    pair = source.review
    endpoints = pair.endpoints
    identity = project_peer_reference_identity(Rs485PeerPairKey(pair.bus_id, pair.pair_id))
    assignments = tuple(
        f"{item.reference}: "
        + (
            ", ".join(f"{pin.pin} on {pin.net or 'unassigned'}" for pin in item.reference_pins)
            if item.reference_pins
            else "no mapped reference pin"
        )
        for item in endpoints
    )
    reference_nets = tuple(
        sorted(
            {item.reference_net for item in endpoints if item.reference_net},
            key=lambda item: (item.casefold(), item),
        )
    )
    evidence = {
        **identity.evidence,
        "line_1": (pair.line_1_net,),
        "line_2": (pair.line_2_net,),
        "participants": tuple(item.reference for item in endpoints),
        "reference_assignments": assignments,
        "reference_nets": reference_nets,
    }
    if pair.incomplete_references:
        evidence["incomplete_reference_evidence"] = pair.incomplete_references
    return CandidateEvidenceProjection(rule_id=_RS485_PEER_REFERENCE, evidence=evidence)


@dataclass(frozen=True, slots=True)
class Rs485PeerReferenceCandidate(PeerReferenceCandidate):
    """RS-485 candidate retaining its source scan, mapped pair, and identity."""

    source_evidence: Rs485PeerReferenceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: Rs485PeerReferenceFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> Rs485PeerReferenceCandidate:
        projection = project_rs485_peer_reference_evidence(source_evidence)
        pair = source_evidence.review
        identity = Rs485PeerPairKey(pair.bus_id, pair.pair_id)
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
        projection = project_rs485_peer_reference_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("RS-485 peer fields must match their typed source projection")
