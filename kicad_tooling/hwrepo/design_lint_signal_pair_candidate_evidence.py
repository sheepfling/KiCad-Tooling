"""Typed signal-pair sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .bus_signal_pairs import ComplementaryLineGap
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .differential_pair_names import NamedDifferentialPair

SignalPairCandidateEvidence: TypeAlias = ComplementaryLineGap | NamedDifferentialPair


def project_signal_pair_evidence(
    source: SignalPairCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project one named pair source to the established report fields."""
    if isinstance(source, ComplementaryLineGap):
        evidence: dict[str, tuple[str, ...]] = {
            "positive_pins": source.positive_pins,
            "negative_pins": source.negative_pins,
            "positive_nets": source.positive_nets,
            "negative_nets": source.negative_nets,
        }
        if source.alias_symbol is not None:
            if source.alias_basis is None or source.alias_sha256 is None:
                raise AssertionError(
                    "Resolved complementary aliases must retain their basis digest"
                )
            evidence.update(
                {
                    "alias_symbol": (source.alias_symbol,),
                    "alias_basis": (source.alias_basis,),
                    "alias_sha256": (source.alias_sha256,),
                }
            )
        return CandidateEvidenceProjection(
            rule_id="bus.complementary_pair_assignment",
            evidence=evidence,
        )
    return CandidateEvidenceProjection(
        rule_id="signal.named_pair_without_reviewed_requirement",
        evidence={
            "positive_net": (source.positive_net,),
            "positive_references": source.positive_references,
            "negative_net": (source.negative_net,),
            "negative_references": source.negative_references,
            "naming_pattern": (source.naming_pattern,),
        },
    )


@dataclass(frozen=True, slots=True)
class SignalPairCandidate(Candidate):
    """Internal signal-pair finding retaining its typed source record."""

    source_evidence: SignalPairCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SignalPairCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> SignalPairCandidate:
        projection = project_signal_pair_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_signal_pair_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Signal-pair rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Signal-pair evidence must match its typed source projection")
