"""Typed evidence for contradictory custom PCB DRC constraint bounds."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import (
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "pcb.custom_drc_contradictory_constraint_bounds"


@dataclass(frozen=True, slots=True)
class PcbDruContradictoryBoundsFindingEvidence:
    """One source-bound constraint whose explicit minimum exceeds its maximum."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    constraint_name: str
    minimum_nm: int
    maximum_nm: int

    def __post_init__(self) -> None:
        if not self.rule_name or self.rule_ordinal < 1:
            raise ValueError("Contradictory custom DRC bounds require a named rule ordinal")
        if self.minimum_nm <= self.maximum_nm or self.maximum_nm <= 0:
            raise ValueError(
                "Contradictory custom DRC bounds require positive min greater than max"
            )
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Contradictory custom DRC bounds require a supported KiCad 10 version")


def project_pcb_dru_contradictory_bounds_evidence(
    source: PcbDruContradictoryBoundsFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact source and parsed bounds into stable report evidence."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "constraint_name": (source.constraint_name,),
            "minimum_nm": (str(source.minimum_nm),),
            "maximum_nm": (str(source.maximum_nm),),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruContradictoryBoundsCandidate(Candidate):
    """Review prompt retaining the contradictory source-bound constraint."""

    source_evidence: PcbDruContradictoryBoundsFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruContradictoryBoundsFindingEvidence,
        *,
        message: str,
    ) -> PcbDruContradictoryBoundsCandidate:
        projection = project_pcb_dru_contradictory_bounds_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.source_file.source_path}#rule"
                f"[{source_evidence.rule_ordinal}] {source_evidence.rule_name}"
                f"/{source_evidence.constraint_name}"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_contradictory_bounds_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Contradictory-bound fields must match their source projection")
