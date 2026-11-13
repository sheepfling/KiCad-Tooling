"""Typed source evidence for empty custom PCB DRC disallow clauses."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import SourceBoundPcbDruRuleFile
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_dru_constraint_type_registry import supports_kicad_10_0_constraint_registry

RULE_ID: DesignLintRuleId = "pcb.custom_drc_empty_disallow_clause"


@dataclass(frozen=True, slots=True)
class PcbDruEmptyDisallowFindingEvidence:
    """One direct ``disallow`` constraint with no literal object types."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    constraint_ordinal: int

    def __post_init__(self) -> None:
        if not self.rule_name or self.rule_ordinal < 1 or self.constraint_ordinal < 1:
            raise ValueError("Empty disallow evidence requires exact source and clause identity")
        if not supports_kicad_10_0_constraint_registry(self.source_file.kicad_version):
            raise ValueError("Empty disallow evidence requires KiCad 10.0.x")


def project_pcb_dru_empty_disallow_evidence(
    source: PcbDruEmptyDisallowFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and the exact empty clause location."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "constraint_ordinal": (str(source.constraint_ordinal),),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruEmptyDisallowCandidate(Candidate):
    """Default-review prompt for a disallow clause with no object operands."""

    source_evidence: PcbDruEmptyDisallowFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruEmptyDisallowFindingEvidence,
        *,
        message: str,
    ) -> PcbDruEmptyDisallowCandidate:
        projection = project_pcb_dru_empty_disallow_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.source_file.source_path}#rule"
                f"[{source_evidence.rule_ordinal}] {source_evidence.rule_name}/constraint"
                f"[{source_evidence.constraint_ordinal}]"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_empty_disallow_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Empty-disallow fields must match their source projection")
