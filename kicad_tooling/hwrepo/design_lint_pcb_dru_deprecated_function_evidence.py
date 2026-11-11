"""Typed source records for deprecated custom DRC condition functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .design_lint_pcb_dru_rule_candidate_evidence import SourceBoundPcbDruRuleFile
from .design_lint_types import Candidate, CandidateEvidenceProjection

PcbDruDeprecatedFunction = Literal[
    "insideArea",
    "insideCourtyard",
    "insideFrontCourtyard",
    "insideBackCourtyard",
    "memberOf",
]


@dataclass(frozen=True, slots=True)
class PcbDruDeprecatedFunctionUse:
    """One documented deprecated condition function and its replacement."""

    function: PcbDruDeprecatedFunction
    replacement: str
    condition_offset: int

    def __post_init__(self) -> None:
        if self.condition_offset < 0:
            raise ValueError("Condition function offsets must be nonnegative")


@dataclass(frozen=True, slots=True)
class PcbDruDeprecatedFunctionFindingEvidence:
    """A named source-bound custom rule using deprecated condition functions."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinal: int
    uses: tuple[PcbDruDeprecatedFunctionUse, ...]

    def __post_init__(self) -> None:
        if not self.rule_name or self.rule_ordinal < 1 or not self.uses:
            raise ValueError("Deprecated-function evidence requires a named rule and uses")
        if tuple(sorted(self.uses, key=lambda item: item.condition_offset)) != self.uses:
            raise ValueError("Deprecated-function uses must preserve condition order")


def project_pcb_dru_deprecated_function_evidence(
    source: PcbDruDeprecatedFunctionFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact rule identity and old-to-new function names for reports."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_deprecated_condition_function",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "deprecated_functions": tuple(use.function for use in source.uses),
            "recommended_functions": tuple(use.replacement for use in source.uses),
            "condition_offsets": tuple(str(use.condition_offset) for use in source.uses),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruDeprecatedFunctionCandidate(Candidate):
    """Custom-rule review candidate retaining typed source and function evidence."""

    source_evidence: PcbDruDeprecatedFunctionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruDeprecatedFunctionFindingEvidence,
        *,
        message: str,
    ) -> PcbDruDeprecatedFunctionCandidate:
        projection = project_pcb_dru_deprecated_function_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.source_file.source_path}"
                f"#rule[{source_evidence.rule_ordinal}] {source_evidence.rule_name}"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_deprecated_function_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Deprecated-function fields must match their source evidence")
