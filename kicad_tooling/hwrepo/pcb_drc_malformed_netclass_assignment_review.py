"""Source-bound review of malformed PCB netclass assignment shapes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_duplicate_net_settings_sections import (
    PcbMalformedNetClassAssignment,
    configured_pcb_malformed_netclass_assignments,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_malformed_netclass_assignment"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassAssignmentEvidence:
    """Malformed assignment shape tied to exact KiCad project settings bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    assignment: PcbMalformedNetClassAssignment

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Malformed netclass evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Malformed netclass evidence requires KiCad 10.0.8")


def project_pcb_malformed_netclass_assignment_evidence(
    source: PcbMalformedNetClassAssignmentEvidence,
) -> CandidateEvidenceProjection:
    """Project the source digest and exact JSON shape evidence."""
    evidence: dict[str, tuple[str, ...]] = {
        "source_path": (source.source_path,),
        "source_sha256": (source.source_sha256,),
        "kicad_version": (source.kicad_version,),
        "project_kind": (source.project_kind.value,),
        "observed_json_type": (source.assignment.observed_json_type,),
    }
    if source.assignment.net_name is not None:
        evidence["net_name"] = (source.assignment.net_name,)
    if source.assignment.malformed_member_indexes:
        evidence["malformed_member_indexes"] = tuple(
            str(index) for index in source.assignment.malformed_member_indexes
        )
        evidence["malformed_member_kinds"] = source.assignment.malformed_member_kinds
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


def _subject(source: PcbMalformedNetClassAssignmentEvidence) -> str:
    subject = f"{source.source_path}#net_settings/netclass_assignments"
    if source.assignment.net_name is not None:
        return f"{subject}/{source.assignment.net_name}"
    return subject


def _message(source: PcbMalformedNetClassAssignmentEvidence) -> str:
    assignment = source.assignment
    if assignment.net_name is None:
        return (
            f"KiCad {source.kicad_version} project settings store netclass_assignments as "
            f"JSON {assignment.observed_json_type}; review the assignment map shape."
        )
    if assignment.malformed_member_indexes:
        details = ", ".join(
            f"{index} ({kind})"
            for index, kind in zip(
                assignment.malformed_member_indexes,
                assignment.malformed_member_kinds,
                strict=True,
            )
        )
        return (
            f"KiCad {source.kicad_version} project settings give net {assignment.net_name!r} "
            f"an assignment array with malformed member(s) at index {details}; review its "
            "class names."
        )
    return (
        f"KiCad {source.kicad_version} project settings give net {assignment.net_name!r} "
        f"a JSON {assignment.observed_json_type} netclass assignment; review its class name."
    )


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassAssignmentCandidate(Candidate):
    """Review candidate from a malformed, source-bound PCB assignment value."""

    source_evidence: PcbMalformedNetClassAssignmentEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbMalformedNetClassAssignmentEvidence,
    ) -> PcbMalformedNetClassAssignmentCandidate:
        projection = project_pcb_malformed_netclass_assignment_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_malformed_netclass_assignment_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Malformed netclass candidate must match source evidence")


def source_bound_pcb_malformed_netclass_assignment_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review unsupported netclass assignment JSON shapes for exact KiCad 10.0.8."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        assignments = configured_pcb_malformed_netclass_assignments(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbMalformedNetClassAssignmentCandidate.from_source_evidence(
            PcbMalformedNetClassAssignmentEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                assignment=assignment,
            )
        )
        for assignment in assignments
    )
