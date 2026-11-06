"""Typed evidence for exact and case-folded custom DRC rule-name reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_pcb_dru_rule_candidate_evidence import (
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection


@dataclass(frozen=True, slots=True)
class PcbDruDuplicateRuleNameFindingEvidence:
    """A source-bound group of custom DRC declarations sharing one exact name."""

    source_file: SourceBoundPcbDruRuleFile
    rule_name: str
    rule_ordinals: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.rule_name:
            raise ValueError("Duplicate custom DRC rule evidence requires a nonempty name")
        if (
            len(self.rule_ordinals) < 2
            or self.rule_ordinals != tuple(sorted(set(self.rule_ordinals)))
            or self.rule_ordinals[0] < 1
        ):
            raise ValueError("Duplicate rule ordinals must be sorted, unique, and contain a pair")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Duplicate custom DRC name review requires a supported KiCad version")


@dataclass(frozen=True, slots=True)
class PcbDruCasefoldRuleNameFindingEvidence:
    """Source-bound declarations whose exact names differ only after case-folding."""

    source_file: SourceBoundPcbDruRuleFile
    casefold_key: str
    rule_names: tuple[str, ...]
    rule_ordinals: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.casefold_key or self.casefold_key != self.casefold_key.casefold():
            raise ValueError("Case-folded custom DRC name evidence requires a canonical key")
        if len(self.rule_names) != len(self.rule_ordinals) or len(set(self.rule_names)) < 2:
            raise ValueError("Case-folded name evidence requires at least two exact names")
        if any(name.casefold() != self.casefold_key for name in self.rule_names):
            raise ValueError("Every exact rule name must match the case-folded evidence key")
        if (
            self.rule_ordinals != tuple(sorted(set(self.rule_ordinals)))
            or self.rule_ordinals[0] < 1
        ):
            raise ValueError("Case-folded rule ordinals must be sorted, unique, and positive")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Case-folded custom DRC name review requires a supported version")


def project_pcb_dru_duplicate_rule_name_evidence(
    source: PcbDruDuplicateRuleNameFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project duplicate rule identity and source ordinals into report evidence."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_duplicate_rule_name",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinals": tuple(str(ordinal) for ordinal in source.rule_ordinals),
        },
    )


def project_pcb_dru_casefold_rule_name_evidence(
    source: PcbDruCasefoldRuleNameFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact rule names, source ordinals, and the case-fold key."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_casefold_rule_name_collision",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "casefold_key": (source.casefold_key,),
            "rule_names": source.rule_names,
            "rule_ordinals": tuple(str(ordinal) for ordinal in source.rule_ordinals),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruDuplicateRuleNameCandidate(Candidate):
    """Duplicate-name prompt retaining exact source identity and declaration ordinals."""

    source_evidence: PcbDruDuplicateRuleNameFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruDuplicateRuleNameFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruDuplicateRuleNameCandidate:
        projection = project_pcb_dru_duplicate_rule_name_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_duplicate_rule_name_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Duplicate rule fields must match their source-bound projection")


@dataclass(frozen=True, slots=True)
class PcbDruCasefoldRuleNameCandidate(Candidate):
    """Potential case-insensitive naming ambiguity with exact source evidence."""

    source_evidence: PcbDruCasefoldRuleNameFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruCasefoldRuleNameFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruCasefoldRuleNameCandidate:
        projection = project_pcb_dru_casefold_rule_name_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_casefold_rule_name_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Case-folded rule fields must match their source-bound projection")
