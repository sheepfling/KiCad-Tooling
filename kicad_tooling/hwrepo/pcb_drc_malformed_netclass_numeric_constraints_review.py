"""Source-bound review of nonnumeric PCB netclass constraint values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_malformed_netclass_numeric_constraints import (
    PcbMalformedNetClassNumericConstraint,
    configured_pcb_malformed_netclass_numeric_constraints,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_malformed_netclass_numeric_constraints"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassNumericConstraintEvidence:
    """Nonnumeric netclass property bound to exact project-settings bytes."""

    source_path: str
    source_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    constraint: PcbMalformedNetClassNumericConstraint

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("PCB netclass constraint evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("PCB netclass constraint evidence requires KiCad 10.0.8")


def project_pcb_malformed_netclass_numeric_constraint_evidence(
    source: PcbMalformedNetClassNumericConstraintEvidence,
) -> CandidateEvidenceProjection:
    """Project source identity and the exact class/property/value location."""
    constraint = source.constraint
    evidence: dict[str, tuple[str, ...]] = {
        "source_path": (source.source_path,),
        "source_sha256": (source.source_sha256,),
        "kicad_version": (source.kicad_version,),
        "project_kind": (source.project_kind.value,),
        "class_index": (str(constraint.class_index),),
        "property": (constraint.property_name,),
        "observed_json_type": (constraint.observed_json_type,),
        "member_occurrence": (str(constraint.member_occurrence),),
    }
    if constraint.class_name is not None:
        evidence["class_name"] = (constraint.class_name,)
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


def _subject(source: PcbMalformedNetClassNumericConstraintEvidence) -> str:
    constraint = source.constraint
    return (
        f"{source.source_path}#net_settings.classes[{constraint.class_index}]"
        f".{constraint.property_name}[{constraint.member_occurrence}]"
    )


def _message(source: PcbMalformedNetClassNumericConstraintEvidence) -> str:
    constraint = source.constraint
    owner = (
        f"class {constraint.class_name!r} at index {constraint.class_index}"
        if constraint.class_name is not None
        else f"class at index {constraint.class_index}"
    )
    return (
        f"KiCad {source.kicad_version} reads PCB netclass constraints from JSON numbers; "
        f"{owner} contains {constraint.property_name} as JSON "
        f"{constraint.observed_json_type} at occurrence {constraint.member_occurrence}. "
        "Review the saved value and its class assignments."
    )


@dataclass(frozen=True, slots=True)
class PcbMalformedNetClassNumericConstraintCandidate(Candidate):
    """Review candidate from a source-hashed nonnumeric constraint member."""

    source_evidence: PcbMalformedNetClassNumericConstraintEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbMalformedNetClassNumericConstraintEvidence,
    ) -> PcbMalformedNetClassNumericConstraintCandidate:
        projection = project_pcb_malformed_netclass_numeric_constraint_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_malformed_netclass_numeric_constraint_evidence(
            self.source_evidence
        )
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Nonnumeric netclass candidate must match source evidence")


def source_bound_pcb_malformed_netclass_numeric_constraint_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review nonnumeric PCB netclass constraints for exact KiCad 10.0.8 projects."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return ()
    try:
        constraints = configured_pcb_malformed_netclass_numeric_constraints(source.document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB project settings: {exc}"
        ) from exc
    verify_source_bound_pcb_project_settings_unchanged(root, source)

    return tuple(
        PcbMalformedNetClassNumericConstraintCandidate.from_source_evidence(
            PcbMalformedNetClassNumericConstraintEvidence(
                source_path=source.source_path,
                source_sha256=source.source_sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                constraint=constraint,
            )
        )
        for constraint in constraints
    )
