"""Typed source evidence for malformed custom PCB DRC constraint bounds."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import (
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "pcb.custom_drc_malformed_constraint_bounds"


@dataclass(frozen=True, slots=True)
class PcbDruMalformedBoundsFindingEvidence:
    """One recognized constraint whose explicit bounds cannot be parsed."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    constraint_name: str
    parser_issue: str

    def __post_init__(self) -> None:
        if not self.rule_name or self.rule_ordinal < 1 or not self.parser_issue:
            raise ValueError("Malformed custom DRC bounds require a named rule and parser issue")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Malformed custom DRC bounds require a supported KiCad 10 version")


def project_pcb_dru_malformed_bounds_evidence(
    source: PcbDruMalformedBoundsFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact custom-rule source and parser diagnostic into evidence."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "constraint_name": (source.constraint_name,),
            "parser_issue": (source.parser_issue,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruMalformedBoundsCandidate(Candidate):
    """Review prompt retaining the parser issue and exact source identity."""

    source_evidence: PcbDruMalformedBoundsFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruMalformedBoundsFindingEvidence,
        *,
        message: str,
    ) -> PcbDruMalformedBoundsCandidate:
        projection = project_pcb_dru_malformed_bounds_evidence(source_evidence)
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
        projection = project_pcb_dru_malformed_bounds_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Malformed-bound fields must match their source projection")
