"""Source-bound review of repeated top-level schematic ERC settings sections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS,
    SchematicErcDuplicateSectionSetting,
    configured_schematic_erc_duplicate_sections,
)
from .schematic_erc_project_settings_evidence import (
    read_source_bound_schematic_erc_settings,
    verify_source_bound_schematic_erc_settings_unchanged,
)
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.erc_duplicate_section"
_SUPPORTED_KICAD_VERSION = "10.0.8"


@dataclass(frozen=True, slots=True)
class SchematicErcDuplicateSectionEvidence:
    """Repeated ERC sections bound to exact saved project-settings bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    setting: SchematicErcDuplicateSectionSetting

    def __post_init__(self) -> None:
        if self.project_kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
            raise ValueError("Duplicate ERC sections require a schematic-capable project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Duplicate ERC sections require audited KiCad 10.0.8 behavior")
        if len(self.setting.source_order_sections_json) < 2:
            raise ValueError("Duplicate ERC-section evidence requires repeated source entries")


def project_schematic_erc_duplicate_section_evidence(
    source: SchematicErcDuplicateSectionEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and each retained ERC section in saved order."""
    sections = source.setting.source_order_sections_json
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "project_section_key": ("erc",),
            "source_order_sections_json": sections,
            "occurrence_count": (str(len(sections)),),
        },
    )


def _candidate_subject(source: SchematicErcDuplicateSectionEvidence) -> str:
    return f"{source.source_path}#erc"


def _candidate_message(source: SchematicErcDuplicateSectionEvidence) -> str:
    count = len(source.setting.source_order_sections_json)
    return (
        f"KiCad {source.kicad_version} project settings repeat the top-level 'erc' section "
        f"{count} times; review the source-order values and retain one intended section."
    )


@dataclass(frozen=True, slots=True)
class SchematicErcDuplicateSectionCandidate(Candidate):
    """Review candidate derived only from source-bound ERC section evidence."""

    source_evidence: SchematicErcDuplicateSectionEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcDuplicateSectionEvidence,
    ) -> SchematicErcDuplicateSectionCandidate:
        projection = project_schematic_erc_duplicate_section_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_duplicate_section_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic ERC duplicate-section fields must match source evidence")


def source_bound_schematic_erc_duplicate_section_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review repeated root ERC sections for the native-audited KiCad patch."""
    if config.kind not in SCHEMATIC_ERC_SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_schematic_erc_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        settings = configured_schematic_erc_duplicate_sections(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC project settings: {exc}"
        ) from exc
    verify_source_bound_schematic_erc_settings_unchanged(root, source)

    return tuple(
        SchematicErcDuplicateSectionCandidate.from_source_evidence(
            SchematicErcDuplicateSectionEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                setting=setting,
            )
        )
        for setting in settings
    )
