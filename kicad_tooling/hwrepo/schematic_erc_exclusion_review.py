"""Source-bound review candidates for persisted schematic ERC exclusions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .evidence import digest
from .project_models import ProjectConfig, ProjectKind
from .schematic_erc_project_settings import (
    SchematicErcExclusion,
    schematic_erc_exclusion_marker_sha256,
    schematic_erc_exclusions,
)
from .source_state_models import SourceHashInventory

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")
_SCHEMATIC_ERC_EXCLUSION_RULE_ID: DesignLintRuleId = "schematic.erc_exclusion_present"
_SUPPORTED_PROJECT_KINDS = frozenset(
    {
        ProjectKind.PCB,
        ProjectKind.SCHEMATIC,
        ProjectKind.SYSTEM_WIRING,
        ProjectKind.HARNESS_INTERFACE,
    }
)


@dataclass(frozen=True, slots=True)
class SchematicErcExclusionFindingEvidence:
    """Retain one parsed exclusion with its exact project-source identity."""

    source_path: str
    source_sha256: str
    kicad_version: str
    exclusion: SchematicErcExclusion


def _candidate_subject(source: SchematicErcExclusionFindingEvidence) -> str:
    marker_hash = schematic_erc_exclusion_marker_sha256(source.exclusion)
    return f"{source.source_path}#erc/erc_exclusions/{marker_hash}"


def _candidate_message(source: SchematicErcExclusionFindingEvidence) -> str:
    comment_state = (
        "with no explanatory comment"
        if not source.exclusion.comment.strip()
        else "with a saved comment"
    )
    return (
        f"A saved schematic ERC exclusion targets {source.exclusion.error_type!r} "
        f"{comment_state}; confirm that the individual exception is still intentional."
    )


def project_schematic_erc_exclusion_evidence(
    source: SchematicErcExclusionFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project captured exclusion input into stable report fields."""
    return CandidateEvidenceProjection(
        rule_id=_SCHEMATIC_ERC_EXCLUSION_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "erc_error_type": (source.exclusion.error_type,),
            "exclusion_marker_sha256": (schematic_erc_exclusion_marker_sha256(source.exclusion),),
            "exclusion_comment": (source.exclusion.comment,),
        },
    )


@dataclass(frozen=True, slots=True)
class SchematicErcExclusionCandidate(Candidate):
    """A review candidate whose fields are derived from source evidence."""

    source_evidence: SchematicErcExclusionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicErcExclusionFindingEvidence,
    ) -> SchematicErcExclusionCandidate:
        projection = project_schematic_erc_exclusion_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_erc_exclusion_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError(
                "Schematic ERC exclusion candidate fields must match their source projection"
            )


def source_bound_schematic_erc_exclusion_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt to recheck each saved schematic ERC exclusion in KiCad 10.0."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if _SUPPORTED_KICAD_VERSION.fullmatch(config.kicad_version) is None:
        return ()

    root = root.resolve()
    relative = str(config.project)
    settings_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if not settings_file.exists():
        if expected_hash is not None:
            raise ValueError("Source-bound KiCad project settings disappeared during inspection")
        return ()
    if not settings_file.is_file():
        raise ValueError("KiCad project settings path is not a regular file")
    if expected_hash is None:
        raise ValueError("KiCad project settings are outside source-bound project inputs")
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings differ from source-bound project inputs")

    try:
        document = settings_file.read_text(encoding="utf-8")
        exclusions = schematic_erc_exclusions(document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported schematic ERC exclusions: {exc}"
        ) from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")

    return tuple(
        SchematicErcExclusionCandidate.from_source_evidence(
            SchematicErcExclusionFindingEvidence(
                source_path=relative,
                source_sha256=expected_hash,
                kicad_version=config.kicad_version,
                exclusion=exclusion,
            )
        )
        for exclusion in exclusions
    )
