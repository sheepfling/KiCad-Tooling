"""Typed source evidence for unknown KiCad custom DRC disallow operands."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import SourceBoundPcbDruRuleFile
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_dru_constraint_type_registry import supports_kicad_10_0_constraint_registry

RULE_ID: DesignLintRuleId = "pcb.custom_drc_unknown_disallowed_object_type"


@dataclass(frozen=True, slots=True)
class PcbDruUnknownDisallowedObjectFindingEvidence:
    """One direct disallow operand outside the KiCad 10.0 object vocabulary."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    constraint_ordinal: int
    object_ordinal: int
    object_type: str

    def __post_init__(self) -> None:
        if (
            not self.rule_name
            or self.rule_ordinal < 1
            or self.constraint_ordinal < 1
            or self.object_ordinal < 1
            or not self.object_type
        ):
            raise ValueError("Unknown disallow objects require source and operand identity")
        if not supports_kicad_10_0_constraint_registry(self.source_file.kicad_version):
            raise ValueError("Unknown disallow object evidence requires KiCad 10.0.x")


def project_pcb_dru_unknown_disallowed_object_evidence(
    source: PcbDruUnknownDisallowedObjectFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact rule source and unrecognized object token."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "constraint_ordinal": (str(source.constraint_ordinal),),
            "object_ordinal": (str(source.object_ordinal),),
            "object_type": (source.object_type,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruUnknownDisallowedObjectCandidate(Candidate):
    """Review prompt retaining an unknown disallow token and source identity."""

    source_evidence: PcbDruUnknownDisallowedObjectFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruUnknownDisallowedObjectFindingEvidence,
        *,
        message: str,
    ) -> PcbDruUnknownDisallowedObjectCandidate:
        projection = project_pcb_dru_unknown_disallowed_object_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.source_file.source_path}#rule"
                f"[{source_evidence.rule_ordinal}] {source_evidence.rule_name}/constraint"
                f"[{source_evidence.constraint_ordinal}]/object"
                f"[{source_evidence.object_ordinal}]"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_unknown_disallowed_object_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Unknown-disallow fields must match their source projection")
