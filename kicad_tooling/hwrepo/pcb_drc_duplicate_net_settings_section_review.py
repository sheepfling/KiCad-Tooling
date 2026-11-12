"""Source-bound review of repeated top-level PCB net_settings sections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_duplicate_net_settings_sections import (
    PcbDuplicateNetSettingsSectionSetting,
    configured_pcb_duplicate_net_settings_sections,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_duplicate_net_settings_section"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbDuplicateNetSettingsSectionEvidence:
    """Repeated net_settings bound to exact KiCad project bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    setting: PcbDuplicateNetSettingsSectionSetting

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Duplicate PCB net_settings sections require a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Duplicate net_settings evidence requires audited KiCad 10.0.8")
        if len(self.setting.source_order_sections_json) < 2:
            raise ValueError("Duplicate net_settings evidence requires repeated source entries")


def project_pcb_drc_duplicate_net_settings_section_evidence(
    source: PcbDuplicateNetSettingsSectionEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and every retained net_settings section."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "project_section_key": ("net_settings",),
            "source_order_sections_json": source.setting.source_order_sections_json,
            "occurrence_count": (str(len(source.setting.source_order_sections_json)),),
        },
    )


def _subject(source: PcbDuplicateNetSettingsSectionEvidence) -> str:
    return f"{source.source_path}#net_settings"


def _message(source: PcbDuplicateNetSettingsSectionEvidence) -> str:
    count = len(source.setting.source_order_sections_json)
    return (
        f"KiCad {source.kicad_version} project settings repeat the top-level 'net_settings' "
        f"section {count} times; review the source-order values and retain one intended section."
    )


@dataclass(frozen=True, slots=True)
class PcbDuplicateNetSettingsSectionCandidate(Candidate):
    """Review candidate derived only from repeated source settings."""

    source_evidence: PcbDuplicateNetSettingsSectionEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDuplicateNetSettingsSectionEvidence,
    ) -> PcbDuplicateNetSettingsSectionCandidate:
        projection = project_pcb_drc_duplicate_net_settings_section_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_duplicate_net_settings_section_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("PCB duplicate net_settings fields must match source evidence")


def source_bound_pcb_drc_duplicate_net_settings_section_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review repeated net_settings for the native-audited KiCad patch."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        settings = configured_pcb_duplicate_net_settings_sections(
            source.document,
            allow_source_bound_duplicates=True,
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbDuplicateNetSettingsSectionCandidate.from_source_evidence(
            PcbDuplicateNetSettingsSectionEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                setting=setting,
            )
        )
        for setting in settings
    )
