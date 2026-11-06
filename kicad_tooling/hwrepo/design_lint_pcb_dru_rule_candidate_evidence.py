"""Typed source records and report projections for custom PCB DRC rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .model_primitives import Digest, RepositoryPath
from .pcb_drc_rule_parser import (
    NativeDrcRuleDeclaration,
    NativeDrcRuleWithConflictingSeverities,
    NativeDrcRuleWithSeverity,
    NativeIgnoredDrcRule,
)
from .project_models import ProjectKind

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.\d+\.\d+\Z")

PcbDruRuleSeverity: TypeAlias = Literal["ignore", "exclusion"]
PcbDruRuleId: TypeAlias = Literal[
    "pcb.custom_drc_rule_ignored",
    "pcb.custom_drc_rule_excluded",
    "pcb.custom_drc_rule_without_constraint",
    "pcb.custom_drc_duplicate_rule_name",
    "pcb.custom_drc_casefold_rule_name_collision",
    "pcb.custom_drc_conflicting_severities",
]
PcbDruParsedRule: TypeAlias = NativeIgnoredDrcRule | NativeDrcRuleWithSeverity
PcbDruInputRole: TypeAlias = Literal["project", "board"]


def is_supported_pcb_dru_kicad_version(version: str) -> bool:
    """Return whether this rule-review route has audited the exact KiCad version form."""
    return _SUPPORTED_KICAD_VERSION.fullmatch(version) is not None


@dataclass(frozen=True, slots=True)
class SourceBoundPcbDruRuleFile:
    """A verified custom rule file plus its repository-local read path."""

    source_path: RepositoryPath
    source_sha256: Digest
    project_kind: ProjectKind
    kicad_version: str
    local_path: Path

    def __post_init__(self) -> None:
        if self.project_kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
            raise ValueError("Custom PCB DRC rules require a PCB project")
        if not self.source_path.endswith(".kicad_dru"):
            raise ValueError("Custom PCB DRC rule source must be a .kicad_dru file")
        if not self.local_path.is_absolute():
            raise ValueError("Custom PCB DRC rule read path must be resolved")


@dataclass(frozen=True, slots=True)
class SourceBoundPcbDruInput:
    """A project or board source identity required to review variable expansion."""

    source_path: RepositoryPath
    source_sha256: Digest
    role: PcbDruInputRole

    def __post_init__(self) -> None:
        suffix = ".kicad_pro" if self.role == "project" else ".kicad_pcb"
        if not self.source_path.endswith(suffix):
            raise ValueError(f"{self.role.title()} source must be a {suffix} file")


@dataclass(frozen=True, slots=True)
class PcbDruRuleFindingEvidence:
    """One parsed custom rule and its source-bound ignore or exclusion declaration."""

    source_file: SourceBoundPcbDruRuleFile
    rule: PcbDruParsedRule
    severity: PcbDruRuleSeverity

    def __post_init__(self) -> None:
        if self.severity == "ignore":
            if not isinstance(self.rule, NativeIgnoredDrcRule):
                raise ValueError("Ignore findings require the canonical ignored-rule parser record")
        elif not (
            isinstance(self.rule, NativeDrcRuleWithSeverity) and self.rule.severity == "exclusion"
        ):
            raise ValueError("Exclusion findings require an exclusion-severity parser record")
        if self.severity == "exclusion" and not is_supported_pcb_dru_kicad_version(
            self.source_file.kicad_version
        ):
            raise ValueError("Custom DRC exclusion review requires a supported KiCad version")

    @property
    def rule_id(self) -> PcbDruRuleId:
        return (
            "pcb.custom_drc_rule_ignored"
            if self.severity == "ignore"
            else "pcb.custom_drc_rule_excluded"
        )


@dataclass(frozen=True, slots=True)
class PcbDruTextVariableFindingEvidence:
    """Unresolved variable names bound to the rule, project, and board source bytes."""

    source_file: SourceBoundPcbDruRuleFile
    project_source: SourceBoundPcbDruInput
    board_source: SourceBoundPcbDruInput
    variable_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.project_source.role != "project" or self.board_source.role != "board":
            raise ValueError("Text-variable evidence requires named project and board sources")
        if self.variable_names != tuple(sorted(set(self.variable_names))):
            raise ValueError("Text-variable names must be sorted and unique")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Custom DRC text-variable review requires a supported KiCad version")


@dataclass(frozen=True, slots=True)
class PcbDruRuleWithoutConstraintFindingEvidence:
    """A source-bound named custom rule with no direct constraint clauses."""

    source_file: SourceBoundPcbDruRuleFile
    rule: NativeDrcRuleDeclaration

    def __post_init__(self) -> None:
        if self.rule.constraint_count != 0:
            raise ValueError("Unconstrained-rule evidence requires zero direct constraints")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Unconstrained custom DRC review requires a supported KiCad version")


@dataclass(frozen=True, slots=True)
class PcbDruConflictingSeveritiesFindingEvidence:
    """A source-bound rule with multiple distinct severity declarations."""

    source_file: SourceBoundPcbDruRuleFile
    rule: NativeDrcRuleWithConflictingSeverities

    def __post_init__(self) -> None:
        if not self.rule.name or self.rule.ordinal < 1:
            raise ValueError("Conflicting-severity evidence requires a named rule ordinal")
        if len(self.rule.severities) < 2 or len(set(self.rule.severities)) < 2:
            raise ValueError("Conflicting-severity evidence requires distinct declarations")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError(
                "Conflicting custom DRC severity review requires a supported KiCad version"
            )


def project_pcb_dru_rule_evidence(
    source: PcbDruRuleFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the preserved custom rule identity into the established report fields."""
    rule = source.rule
    evidence: dict[str, tuple[str, ...]] = {
        "source_path": (source.source_file.source_path,),
        "source_sha256": (source.source_file.source_sha256,),
        "kicad_version": (source.source_file.kicad_version,),
        "rule_name": (rule.name,),
        "rule_ordinal": (str(rule.ordinal),),
    }
    if source.severity == "exclusion":
        evidence["severity"] = ("exclusion",)
    return CandidateEvidenceProjection(rule_id=source.rule_id, evidence=evidence)


def project_pcb_dru_text_variable_evidence(
    source: PcbDruTextVariableFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project unresolved substitutions with exact identities for all three inputs."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_text_variable_review",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "project_path": (source.project_source.source_path,),
            "project_sha256": (source.project_source.source_sha256,),
            "board_path": (source.board_source.source_path,),
            "board_sha256": (source.board_source.source_sha256,),
            "variable_names": source.variable_names,
            "kicad_version": (source.source_file.kicad_version,),
        },
    )


def project_pcb_dru_rule_without_constraint_evidence(
    source: PcbDruRuleWithoutConstraintFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project an unconstrained rule with exact source and declaration identity."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_rule_without_constraint",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule.name,),
            "rule_ordinal": (str(source.rule.ordinal),),
            "constraint_count": (str(source.rule.constraint_count),),
        },
    )


def project_pcb_dru_conflicting_severities_evidence(
    source: PcbDruConflictingSeveritiesFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and severity declaration order into report evidence."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_conflicting_severities",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule.name,),
            "rule_ordinal": (str(source.rule.ordinal),),
            "severities": source.rule.severities,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruRuleCandidate(Candidate):
    """Custom-rule candidate retaining the parsed, source-bound rule record."""

    source_evidence: PcbDruRuleFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruRuleFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruRuleCandidate:
        projection = project_pcb_dru_rule_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_rule_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Custom DRC rule fields must match their source-bound projection")


@dataclass(frozen=True, slots=True)
class PcbDruTextVariableCandidate(Candidate):
    """Text-variable review candidate retaining each exact source identity."""

    source_evidence: PcbDruTextVariableFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruTextVariableFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruTextVariableCandidate:
        projection = project_pcb_dru_text_variable_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_text_variable_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Text-variable fields must match their source-bound projection")


@dataclass(frozen=True, slots=True)
class PcbDruRuleWithoutConstraintCandidate(Candidate):
    """Unconstrained-rule review candidate retaining parsed source evidence."""

    source_evidence: PcbDruRuleWithoutConstraintFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruRuleWithoutConstraintFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruRuleWithoutConstraintCandidate:
        projection = project_pcb_dru_rule_without_constraint_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_rule_without_constraint_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Unconstrained-rule fields must match their source-bound projection")


@dataclass(frozen=True, slots=True)
class PcbDruConflictingSeveritiesCandidate(Candidate):
    """Severity-conflict prompt retaining typed source-bound rule evidence."""

    source_evidence: PcbDruConflictingSeveritiesFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruConflictingSeveritiesFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDruConflictingSeveritiesCandidate:
        projection = project_pcb_dru_conflicting_severities_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_conflicting_severities_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Conflicting-severity fields must match their source-bound projection")
