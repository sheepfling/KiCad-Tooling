"""Source-bound review of PCB net assignments to undeclared netclasses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_duplicate_net_settings_sections import (
    PcbUnresolvedNetClassAssignment,
    configured_pcb_unresolved_netclass_assignments,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_unresolved_netclass_assignment"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbUnresolvedNetClassAssignmentEvidence:
    """Undeclared class target tied to exact KiCad project settings bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    assignment: PcbUnresolvedNetClassAssignment

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Unresolved netclass evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Unresolved netclass evidence requires KiCad 10.0.8")
        if self.assignment.assigned_class in self.assignment.declared_class_names:
            raise ValueError("Unresolved netclass evidence must name a missing class")


def project_pcb_unresolved_netclass_assignment_evidence(
    source: PcbUnresolvedNetClassAssignmentEvidence,
) -> CandidateEvidenceProjection:
    """Project the source digest, net, requested class, and complete class inventory."""
    evidence = {
        "source_path": (source.source_path,),
        "source_sha256": (source.source_sha256,),
        "kicad_version": (source.kicad_version,),
        "project_kind": (source.project_kind.value,),
        "net_name": (source.assignment.net_name,),
        "assigned_class": (source.assignment.assigned_class,),
        "declared_class_names": source.assignment.declared_class_names,
    }
    if source.assignment.assigned_classes:
        evidence["assigned_classes"] = source.assignment.assigned_classes
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence=evidence,
    )


def _subject(source: PcbUnresolvedNetClassAssignmentEvidence) -> str:
    return f"{source.source_path}#net_settings/netclass_assignments/{source.assignment.net_name}"


def _message(source: PcbUnresolvedNetClassAssignmentEvidence) -> str:
    return (
        f"KiCad {source.kicad_version} project settings assign net "
        f"{source.assignment.net_name!r} to undeclared netclass "
        f"{source.assignment.assigned_class!r}; review the class name or restore its definition."
    )


@dataclass(frozen=True, slots=True)
class PcbUnresolvedNetClassAssignmentCandidate(Candidate):
    """Review candidate from complete, source-bound PCB netclass settings."""

    source_evidence: PcbUnresolvedNetClassAssignmentEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbUnresolvedNetClassAssignmentEvidence,
    ) -> PcbUnresolvedNetClassAssignmentCandidate:
        projection = project_pcb_unresolved_netclass_assignment_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_unresolved_netclass_assignment_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Unresolved netclass candidate must match source evidence")


def source_bound_pcb_unresolved_netclass_assignment_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review unresolved PCB netclass names for exact KiCad 10.0.8 projects."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        assignments = configured_pcb_unresolved_netclass_assignments(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbUnresolvedNetClassAssignmentCandidate.from_source_evidence(
            PcbUnresolvedNetClassAssignmentEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                assignment=assignment,
            )
        )
        for assignment in assignments
    )
