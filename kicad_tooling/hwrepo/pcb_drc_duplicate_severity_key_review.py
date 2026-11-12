"""Source-bound review of duplicate PCB DRC severity-map keys."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_project_settings import (
    PcbDrcDuplicateRuleSeveritySetting,
    configured_pcb_drc_duplicate_rule_severity_settings,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_duplicate_severity_key"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbDrcDuplicateSeverityKeyEvidence:
    """One repeated DRC severity key bound to the saved settings source."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    setting: PcbDrcDuplicateRuleSeveritySetting

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Duplicate PCB DRC severity keys require a PCB-capable project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Duplicate PCB DRC severity keys require audited KiCad 10.0.8")
        if len(self.setting.configured_values_json) < 2:
            raise ValueError("Duplicate DRC severity evidence requires repeated source entries")


def project_pcb_drc_duplicate_severity_key_evidence(
    source: PcbDrcDuplicateSeverityKeyEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and every repeated value in its saved order."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "drc_severity_key": (source.setting.check_id,),
            "configured_values_json": source.setting.configured_values_json,
            "occurrence_count": (str(len(source.setting.configured_values_json)),),
        },
    )


def _candidate_subject(source: PcbDrcDuplicateSeverityKeyEvidence) -> str:
    return f"{source.source_path}#board/design_settings/rule_severities/{source.setting.check_id}"


def _candidate_message(source: PcbDrcDuplicateSeverityKeyEvidence) -> str:
    count = len(source.setting.configured_values_json)
    return (
        f"KiCad {source.kicad_version} project settings repeat DRC severity key "
        f"{source.setting.check_id!r} {count} times; review the source-order values and "
        "retain one explicitly reviewed entry."
    )


@dataclass(frozen=True, slots=True)
class PcbDrcDuplicateSeverityKeyCandidate(Candidate):
    """A review candidate whose public fields derive from source-bound settings."""

    source_evidence: PcbDrcDuplicateSeverityKeyEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDrcDuplicateSeverityKeyEvidence,
    ) -> PcbDrcDuplicateSeverityKeyCandidate:
        projection = project_pcb_drc_duplicate_severity_key_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_duplicate_severity_key_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("PCB DRC duplicate-key fields must match source evidence")


def source_bound_pcb_drc_duplicate_severity_key_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review repeated DRC severity keys in exact KiCad 10.0.8 project settings."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        settings = configured_pcb_drc_duplicate_rule_severity_settings(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbDrcDuplicateSeverityKeyCandidate.from_source_evidence(
            PcbDrcDuplicateSeverityKeyEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                setting=setting,
            )
        )
        for setting in settings
    )
