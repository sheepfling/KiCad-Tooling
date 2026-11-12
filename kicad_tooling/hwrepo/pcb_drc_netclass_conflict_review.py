"""Source-bound review of conflicting KiCad PCB netclass definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_duplicate_net_settings_sections import (
    PcbConflictingNetClassSettings,
    configured_pcb_conflicting_netclass_settings,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_conflicting_netclass_definitions"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbNetClassConflictEvidence:
    """Conflicting netclass source values tied to exact project bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    setting: PcbConflictingNetClassSettings

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("PCB netclass conflict evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("PCB netclass conflict evidence requires KiCad 10.0.8")
        if len(self.setting.source_order_values_json) < 2:
            raise ValueError("PCB netclass conflict evidence requires conflicting values")
        if self.setting.conflict_scope not in {"classes_member", "class_name", "class_property"}:
            raise ValueError("Unsupported PCB netclass conflict scope")
        if self.setting.conflict_scope == "classes_member":
            if self.setting.class_name is not None or self.setting.property_name is not None:
                raise ValueError("PCB netclass list evidence cannot identify one class property")
        elif not self.setting.class_name:
            raise ValueError("PCB netclass conflict evidence requires its class name")
        elif (self.setting.conflict_scope == "class_property") != bool(self.setting.property_name):
            raise ValueError("PCB netclass property evidence does not match its conflict scope")


def project_pcb_netclass_conflict_evidence(
    source: PcbNetClassConflictEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and every conflicting class value."""
    evidence: dict[str, tuple[str, ...]] = {
        "source_path": (source.source_path,),
        "source_sha256": (source.source_sha256,),
        "kicad_version": (source.kicad_version,),
        "project_kind": (source.project_kind.value,),
        "conflict_scope": (source.setting.conflict_scope,),
        "source_order_values_json": source.setting.source_order_values_json,
        "occurrence_count": (str(len(source.setting.source_order_values_json)),),
    }
    if source.setting.class_name is not None:
        evidence["class_name"] = (source.setting.class_name,)
    if source.setting.property_name is not None:
        evidence["property_name"] = (source.setting.property_name,)
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


def _subject(source: PcbNetClassConflictEvidence) -> str:
    subject = f"{source.source_path}#net_settings/classes"
    if source.setting.property_name is not None:
        return f"{subject}/{source.setting.class_name}/{source.setting.property_name}"
    if source.setting.class_name is not None:
        return f"{subject}/{source.setting.class_name}"
    return subject


def _message(source: PcbNetClassConflictEvidence) -> str:
    if source.setting.class_name is None:
        return (
            f"KiCad {source.kicad_version} project settings repeat the net_settings.classes "
            "member with conflicting values; review source order and retain one intended list."
        )
    if source.setting.property_name is not None:
        return (
            f"KiCad {source.kicad_version} project settings define netclass "
            f"{source.setting.class_name!r} with conflicting duplicate "
            f"{source.setting.property_name!r} values; review source order and retain one value."
        )
    return (
        f"KiCad {source.kicad_version} project settings define netclass "
        f"{source.setting.class_name!r} with conflicting values; review source order and retain "
        "one intended definition."
    )


@dataclass(frozen=True, slots=True)
class PcbNetClassConflictCandidate(Candidate):
    """Review candidate derived only from source-bound PCB project settings."""

    source_evidence: PcbNetClassConflictEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbNetClassConflictEvidence,
    ) -> PcbNetClassConflictCandidate:
        projection = project_pcb_netclass_conflict_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_netclass_conflict_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("PCB netclass conflict fields must match source evidence")


def source_bound_pcb_netclass_conflict_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review conflicting netclass definitions for exact KiCad 10.0.8 projects."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        settings = configured_pcb_conflicting_netclass_settings(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbNetClassConflictCandidate.from_source_evidence(
            PcbNetClassConflictEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                setting=setting,
            )
        )
        for setting in settings
    )
