"""Source-bound review candidates for persisted PCB DRC exclusions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .contracts import repo_path
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .evidence import digest
from .pcb_drc_project_settings import PcbDrcExclusion, pcb_drc_exclusions
from .project_models import (
    ProjectConfig,
    ProjectKind,
)
from .source_state_models import SourceHashInventory

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")
_PCB_DRC_EXCLUSION_RULE_ID: DesignLintRuleId = "pcb.drc_exclusion_present"


@dataclass(frozen=True, slots=True)
class PcbDrcExclusionFindingEvidence:
    """Retain one parsed exclusion with its exact project-source identity."""

    source_path: str
    source_sha256: str
    kicad_version: str
    exclusion: PcbDrcExclusion


def _exclusion_marker_sha256(source: PcbDrcExclusionFindingEvidence) -> str:
    return hashlib.sha256(source.exclusion.marker.encode("utf-8")).hexdigest()


def _exclusion_rule_key(source: PcbDrcExclusionFindingEvidence) -> str:
    return source.exclusion.marker.partition("|")[0]


def _candidate_subject(source: PcbDrcExclusionFindingEvidence) -> str:
    return (
        f"{source.source_path}#board/design_settings/"
        f"drc_exclusions/{_exclusion_marker_sha256(source)}"
    )


def _candidate_message(source: PcbDrcExclusionFindingEvidence) -> str:
    comment_state = (
        "with no explanatory comment"
        if not source.exclusion.comment.strip()
        else "with a saved comment"
    )
    return (
        f"A saved per-violation DRC exclusion targets {_exclusion_rule_key(source)!r} "
        f"{comment_state}; confirm the individual violation and its exception are still intentional."
    )


def project_pcb_drc_exclusion_evidence(
    source: PcbDrcExclusionFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project captured exclusion input into the stable candidate fields."""
    return CandidateEvidenceProjection(
        rule_id=_PCB_DRC_EXCLUSION_RULE_ID,
        evidence={
            "source_path": (source.source_path,),
            "source_sha256": (source.source_sha256,),
            "kicad_version": (source.kicad_version,),
            "drc_rule_key": (_exclusion_rule_key(source),),
            "exclusion_marker_sha256": (_exclusion_marker_sha256(source),),
            "serialized_marker": (source.exclusion.marker,),
            "exclusion_comment": (source.exclusion.comment,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDrcExclusionCandidate(Candidate):
    """A review candidate whose report fields are derived from source evidence."""

    source_evidence: PcbDrcExclusionFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDrcExclusionFindingEvidence,
    ) -> PcbDrcExclusionCandidate:
        projection = project_pcb_drc_exclusion_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_candidate_subject(source_evidence),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_drc_exclusion_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _candidate_subject(self.source_evidence)
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError(
                "PCB DRC exclusion candidate fields must match their source projection"
            )


def source_bound_pcb_drc_exclusion_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt to recheck each saved per-violation DRC exclusion in KiCad 10.0."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
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
        exclusions = pcb_drc_exclusions(document)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(f"{relative}: could not read supported PCB DRC exclusions: {exc}") from exc
    if digest(settings_file) != expected_hash:
        raise ValueError("KiCad project settings changed during design-lint inspection")

    candidates: list[Candidate] = []
    for exclusion in exclusions:
        source_evidence = PcbDrcExclusionFindingEvidence(
            source_path=relative,
            source_sha256=expected_hash,
            kicad_version=config.kicad_version,
            exclusion=exclusion,
        )
        candidates.append(PcbDrcExclusionCandidate.from_source_evidence(source_evidence))
    return tuple(candidates)
