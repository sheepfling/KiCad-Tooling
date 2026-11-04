"""Typed source projections for unmapped SPI roster candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .spi_participants import SpiRosterContext, UnmappedSpiParticipant


@dataclass(frozen=True, slots=True)
class UnmappedSpiParticipantFindingEvidence:
    """One discovered SPI endpoint and its authored roster scope."""

    participant: UnmappedSpiParticipant
    scope: SpiRosterContext


_SPI_UNMAPPED_PARTICIPANT: DesignLintRuleId = "bus.spi_unmapped_participant"


def project_unmapped_spi_participant_evidence(
    source: UnmappedSpiParticipantFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project one roster endpoint into the existing finding evidence fields."""
    participant = source.participant
    evidence = {
        "SCK_pins": participant.clock_pins,
        "input_data_pins": participant.input_data_pins,
        "output_data_pins": participant.output_data_pins,
        "chip_select_pins": participant.chip_select_pins,
        "assigned_signal_pins": participant.signal_assignments,
        "SPI_roster_state": (source.scope.state,),
    }
    if source.scope.source_path is not None:
        evidence["electrical_contract_path"] = (source.scope.source_path,)
    if source.scope.source_sha256 is not None:
        evidence["electrical_contract_sha256"] = (source.scope.source_sha256,)
    return CandidateEvidenceProjection(
        rule_id=_SPI_UNMAPPED_PARTICIPANT,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UnmappedSpiParticipantCandidate(Candidate):
    """SPI coverage prompt retaining its exact endpoint and roster scope."""

    source_evidence: UnmappedSpiParticipantFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UnmappedSpiParticipantFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnmappedSpiParticipantCandidate:
        projection = project_unmapped_spi_participant_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_unmapped_spi_participant_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI participant fields must match their typed source projection")
