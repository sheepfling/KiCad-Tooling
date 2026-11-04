"""Typed source projections for SPI chip-select bias review findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .spi_bias_heuristics import SpiChipSelectBiasGap


@dataclass(frozen=True, slots=True)
class SpiBiasFindingEvidence:
    """One exact SPI bias gap returned by the SPI heuristic scan."""

    gap: SpiChipSelectBiasGap


_SPI_BIAS_RULE: DesignLintRuleId = "bus.spi_active_low_chip_select_without_pullup"


def project_spi_bias_evidence(
    source: SpiBiasFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed SPI gap into the established review evidence fields."""
    return CandidateEvidenceProjection(
        rule_id=_SPI_BIAS_RULE,
        evidence={
            "net": (source.gap.net,),
            "active_low_chip_select_pins": source.gap.pins,
            "recognized_positive_rails": source.gap.positive_rails,
            "visible_pullup_paths": (),
        },
    )


@dataclass(frozen=True, slots=True)
class SpiBiasCandidate(Candidate):
    """SPI bias review candidate retaining its heuristic source record."""

    source_evidence: SpiBiasFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SpiBiasFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SpiBiasCandidate:
        projection = project_spi_bias_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_spi_bias_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI bias fields must match their typed source projection")
