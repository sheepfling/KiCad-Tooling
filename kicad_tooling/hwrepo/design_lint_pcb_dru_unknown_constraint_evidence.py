"""Typed source evidence for unknown custom PCB DRC constraint names."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import SourceBoundPcbDruRuleFile
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_dru_constraint_type_registry import supports_kicad_10_0_constraint_registry

RULE_ID: DesignLintRuleId = "pcb.custom_drc_unknown_constraint_type"


@dataclass(frozen=True, slots=True)
class PcbDruUnknownConstraintFindingEvidence:
    """One direct constraint clause whose name is outside the KiCad 10.0 registry."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    constraint_ordinal: int
    constraint_type: str

    def __post_init__(self) -> None:
        if (
            not self.rule_name
            or self.rule_ordinal < 1
            or self.constraint_ordinal < 1
            or not self.constraint_type
        ):
            raise ValueError("Unknown custom DRC constraints require source and clause identity")
        if not supports_kicad_10_0_constraint_registry(self.source_file.kicad_version):
            raise ValueError("Unknown custom DRC constraint evidence requires KiCad 10.0.x")


def project_pcb_dru_unknown_constraint_evidence(
    source: PcbDruUnknownConstraintFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact rule source and unrecognized constraint token."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "constraint_ordinal": (str(source.constraint_ordinal),),
            "constraint_type": (source.constraint_type,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruUnknownConstraintCandidate(Candidate):
    """Review prompt retaining the unknown token and exact source identity."""

    source_evidence: PcbDruUnknownConstraintFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruUnknownConstraintFindingEvidence,
        *,
        message: str,
    ) -> PcbDruUnknownConstraintCandidate:
        projection = project_pcb_dru_unknown_constraint_evidence(source_evidence)
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
        projection = project_pcb_dru_unknown_constraint_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Unknown-constraint fields must match their source projection")
