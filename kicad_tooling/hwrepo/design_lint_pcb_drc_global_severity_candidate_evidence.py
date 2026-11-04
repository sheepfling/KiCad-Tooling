"""Typed source records and projections for PCB DRC severity reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .model_primitives import Digest, RepositoryPath
from .pcb_drc_project_settings import (
    CORE_DRC_CHECK_IDS,
    DFM_ERROR_DEFAULT_DRC_CHECK_IDS,
    ELECTRICAL_ERROR_DEFAULT_DRC_CHECK_IDS,
    MISCELLANEOUS_ERROR_DEFAULT_DRC_CHECK_IDS,
    SIGNAL_INTEGRITY_ERROR_DEFAULT_DRC_CHECK_IDS,
    WARNING_DEFAULT_DRC_CHECK_IDS,
    PcbDrcCheckSeverity,
)
from .project_models import ProjectKind

PcbDrcSeverityCategory: TypeAlias = Literal[
    "core",
    "dfm",
    "warning_default",
    "signal_integrity",
    "electrical",
    "miscellaneous",
]
PcbDrcSeverityRuleId: TypeAlias = Literal[
    "pcb.core_drc_check_ignored",
    "pcb.dfm_drc_check_ignored",
    "pcb.core_drc_check_warning",
    "pcb.dfm_drc_check_warning",
    "pcb.warning_default_drc_check_ignored",
    "pcb.signal_integrity_drc_check_downgraded",
    "pcb.electrical_drc_check_downgraded",
    "pcb.miscellaneous_drc_check_downgraded",
]

WARNING_DEFAULT_DRC_SUPPORTED_VERSIONS = frozenset(
    {"10.0.0", "10.0.3", "10.0.4", "10.0.5", "10.0.6", "10.0.7"}
)


@dataclass(frozen=True, slots=True)
class SourceBoundPcbDrcSettings:
    """Parsed DRC settings tied to the exact source path, digest, kind, and version."""

    project_path: RepositoryPath
    source_sha256: Digest
    project_kind: ProjectKind
    kicad_version: str
    configured_severities: tuple[PcbDrcCheckSeverity, ...]

    def __post_init__(self) -> None:
        if self.project_kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
            raise ValueError("Global PCB DRC settings require a PCB project")
        if not self.kicad_version.startswith("10."):
            raise ValueError("Global PCB DRC settings require a supported KiCad 10 version")
        check_ids = tuple(item.check_id for item in self.configured_severities)
        if check_ids != tuple(sorted(set(check_ids))):
            raise ValueError("Configured DRC severities must retain sorted unique check IDs")


@dataclass(frozen=True, slots=True)
class PcbDrcSeverityFindingEvidence:
    """One source-bound check severity selected by its review category and policy."""

    settings: SourceBoundPcbDrcSettings
    configured_check: PcbDrcCheckSeverity
    category: PcbDrcSeverityCategory
    rule_id: PcbDrcSeverityRuleId

    def __post_init__(self) -> None:
        if self.configured_check not in self.settings.configured_severities:
            raise ValueError("DRC severity finding must belong to the source-bound settings")

        category_check_ids = _category_check_ids(self.category)
        if self.configured_check.check_id not in category_check_ids:
            raise ValueError("DRC check ID must belong to its declared review category")
        if not _rule_matches_configured_severity(
            self.rule_id, self.category, self.configured_check.configured_severity
        ):
            raise ValueError("DRC severity finding rule must match its category and severity")

        if self.category == "core":
            if not self.settings.kicad_version.startswith("10."):
                raise ValueError("Core DRC severity review requires KiCad 10")
        elif self.category == "warning_default":
            if self.settings.kicad_version not in WARNING_DEFAULT_DRC_SUPPORTED_VERSIONS:
                raise ValueError(
                    "Warning-default DRC review requires an explicitly supported version"
                )
        elif not self.settings.kicad_version.startswith("10.0."):
            raise ValueError("Specialized DRC severity review requires KiCad 10.0")


def _category_check_ids(category: PcbDrcSeverityCategory) -> frozenset[str]:
    if category == "core":
        return CORE_DRC_CHECK_IDS
    if category == "dfm":
        return DFM_ERROR_DEFAULT_DRC_CHECK_IDS
    if category == "warning_default":
        return WARNING_DEFAULT_DRC_CHECK_IDS
    if category == "signal_integrity":
        return SIGNAL_INTEGRITY_ERROR_DEFAULT_DRC_CHECK_IDS
    if category == "electrical":
        return ELECTRICAL_ERROR_DEFAULT_DRC_CHECK_IDS
    return MISCELLANEOUS_ERROR_DEFAULT_DRC_CHECK_IDS


def _rule_matches_configured_severity(
    rule_id: PcbDrcSeverityRuleId,
    category: PcbDrcSeverityCategory,
    configured_severity: str,
) -> bool:
    if rule_id == "pcb.core_drc_check_ignored":
        return category == "core" and configured_severity == "ignore"
    if rule_id == "pcb.dfm_drc_check_ignored":
        return category == "dfm" and configured_severity == "ignore"
    if rule_id == "pcb.core_drc_check_warning":
        return category == "core" and configured_severity == "warning"
    if rule_id == "pcb.dfm_drc_check_warning":
        return category == "dfm" and configured_severity == "warning"
    if rule_id == "pcb.warning_default_drc_check_ignored":
        return category == "warning_default" and configured_severity == "ignore"
    if rule_id == "pcb.signal_integrity_drc_check_downgraded":
        return category == "signal_integrity" and configured_severity in {"ignore", "warning"}
    if rule_id == "pcb.electrical_drc_check_downgraded":
        return category == "electrical" and configured_severity in {"ignore", "warning"}
    if rule_id == "pcb.miscellaneous_drc_check_downgraded":
        return category == "miscellaneous" and configured_severity in {"ignore", "warning"}
    return False


def project_pcb_drc_severity_evidence(
    source: PcbDrcSeverityFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project verified settings identity and one selected check into report fields."""
    return CandidateEvidenceProjection(
        rule_id=source.rule_id,
        evidence={
            "source_path": (source.settings.project_path,),
            "source_sha256": (source.settings.source_sha256,),
            "kicad_version": (source.settings.kicad_version,),
            "check_id": (source.configured_check.check_id,),
            "configured_severity": (source.configured_check.configured_severity,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDrcSeverityCandidate(Candidate):
    """Severity review candidate retaining the exact source-bound settings record."""

    source_evidence: PcbDrcSeverityFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDrcSeverityFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDrcSeverityCandidate:
        projection = project_pcb_drc_severity_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_severity_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("DRC severity fields must match their source-bound projection")
