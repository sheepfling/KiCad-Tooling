"""Source-bound review of netclass patterns that match no board net."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_board_source_binding import (
    read_source_bound_pcb_board,
    verify_source_bound_pcb_board_unchanged,
)
from .pcb_drc_netclass_patterns import (
    PcbUnmatchedNetClassPattern,
    unmatched_pcb_netclass_patterns,
)
from .pcb_drc_project_settings_evidence import (
    read_source_bound_pcb_project_settings,
    verify_source_bound_pcb_project_settings_unchanged,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "pcb.drc_netclass_pattern_unmatched"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_SUPPORTED_PROJECT_KINDS = frozenset({ProjectKind.PCB, ProjectKind.PCB_ONLY})


@dataclass(frozen=True, slots=True)
class PcbUnmatchedNetClassPatternEvidence:
    """A netclass pattern and both source identities used to check it."""

    project_path: str
    project_sha256: str
    board_path: str
    board_sha256: str
    kicad_version: str
    project_kind: ProjectKind
    pattern: PcbUnmatchedNetClassPattern

    def __post_init__(self) -> None:
        if self.project_kind not in _SUPPORTED_PROJECT_KINDS:
            raise ValueError("Unmatched netclass pattern evidence requires a PCB project")
        if self.kicad_version != _SUPPORTED_KICAD_VERSION:
            raise ValueError("Unmatched netclass pattern evidence requires KiCad 10.0.8")
        if self.pattern.pattern_index < 0 or not self.pattern.pattern or not self.pattern.netclass:
            raise ValueError("Unmatched netclass pattern evidence requires a complete pattern")


def project_pcb_unmatched_netclass_pattern_evidence(
    source: PcbUnmatchedNetClassPatternEvidence,
) -> CandidateEvidenceProjection:
    """Project exact project/board source identities and the unmatched rule."""
    return CandidateEvidenceProjection(
        rule_id=_RULE_ID,
        evidence={
            "project_path": (source.project_path,),
            "project_sha256": (source.project_sha256,),
            "board_path": (source.board_path,),
            "board_sha256": (source.board_sha256,),
            "kicad_version": (source.kicad_version,),
            "project_kind": (source.project_kind.value,),
            "pattern_index": (str(source.pattern.pattern_index),),
            "pattern": (source.pattern.pattern,),
            "netclass": (source.pattern.netclass,),
        },
    )


def _subject(source: PcbUnmatchedNetClassPatternEvidence) -> str:
    return f"{source.project_path}#net_settings/netclass_patterns/{source.pattern.pattern_index}"


def _message(source: PcbUnmatchedNetClassPatternEvidence) -> str:
    pattern = source.pattern
    return (
        f"KiCad {source.kicad_version} netclass pattern {pattern.pattern!r} for class "
        f"{pattern.netclass!r} matches no named net in {source.board_path}; review for a stale "
        "or misspelled pattern, or suppress it if the rule is intentionally reserved for future nets."
    )


@dataclass(frozen=True, slots=True)
class PcbUnmatchedNetClassPatternCandidate(Candidate):
    """Review candidate derived from source-matched settings and board nets."""

    source_evidence: PcbUnmatchedNetClassPatternEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbUnmatchedNetClassPatternEvidence,
    ) -> PcbUnmatchedNetClassPatternCandidate:
        projection = project_pcb_unmatched_netclass_pattern_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=_subject(source_evidence),
            message=_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_unmatched_netclass_pattern_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != _subject(self.source_evidence)
            or self.message != _message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Unmatched netclass pattern candidate must match source evidence")


def source_bound_pcb_netclass_pattern_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review supported patterns with no current net match on exact KiCad 10.0.8."""
    if config.kind not in _SUPPORTED_PROJECT_KINDS:
        return ()
    if config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    project_path = str(config.project)
    project = read_source_bound_pcb_project_settings(root, project_path, source_hashes)
    board = read_source_bound_pcb_board(root, config, source_hashes)
    if project is None or board is None:
        return ()
    try:
        board_document = board.source.decode("utf-8")
    except UnicodeError:
        return ()
    patterns = unmatched_pcb_netclass_patterns(project.document, board_document)
    verify_source_bound_pcb_project_settings_unchanged(root, project)
    verify_source_bound_pcb_board_unchanged(board)

    return tuple(
        PcbUnmatchedNetClassPatternCandidate.from_source_evidence(
            PcbUnmatchedNetClassPatternEvidence(
                project_path=project.source_path,
                project_sha256=project.source_sha256,
                board_path=board.relative_path,
                board_sha256=board.sha256,
                kicad_version=config.kicad_version,
                project_kind=config.kind,
                pattern=pattern,
            )
        )
        for pattern in patterns
    )
