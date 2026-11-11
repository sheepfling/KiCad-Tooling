"""Typed evidence for custom DRC layer-name review candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .design_lint_pcb_dru_rule_candidate_evidence import (
    SourceBoundPcbDruInput,
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

PcbDruLayerIssueKind = Literal[
    "display_alias",
    "unknown_layer",
    "layer_not_in_board",
]
PcbDruLayerLocation = Literal["layer_clause", "condition"]


@dataclass(frozen=True, slots=True)
class PcbDruLayerIssue:
    """One noncanonical or unmatched layer reference in a named rule."""

    layer_name: str
    kind: PcbDruLayerIssueKind
    location: PcbDruLayerLocation
    canonical_layer: str | None = None

    def __post_init__(self) -> None:
        if not self.layer_name:
            raise ValueError("Custom DRC layer evidence requires a layer name")
        if (self.kind == "display_alias") != (self.canonical_layer is not None):
            raise ValueError("Only display-alias evidence has a canonical layer name")


@dataclass(frozen=True, slots=True)
class PcbDruLayerFindingEvidence:
    """Exact DRC and board inputs plus the layer references under review."""

    source_file: SourceBoundPcbDruRuleFile
    board_source: SourceBoundPcbDruInput
    rule_name: str
    rule_ordinal: int
    issues: tuple[PcbDruLayerIssue, ...]

    def __post_init__(self) -> None:
        if self.board_source.role != "board":
            raise ValueError("Custom DRC layer evidence requires the exact PCB source")
        if not self.rule_name or self.rule_ordinal < 1 or not self.issues:
            raise ValueError("Custom DRC layer findings require a named rule and issue")
        if not is_supported_pcb_dru_kicad_version(self.source_file.kicad_version):
            raise ValueError("Custom DRC layer review requires a supported KiCad version")


def project_pcb_dru_layer_evidence(
    source: PcbDruLayerFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project source, board, rule, and layer identities into report evidence."""
    return CandidateEvidenceProjection(
        rule_id="pcb.custom_drc_layer_reference",
        evidence={
            "source_path": (source.source_file.source_path,),
            "source_sha256": (source.source_file.source_sha256,),
            "board_path": (source.board_source.source_path,),
            "board_sha256": (source.board_source.source_sha256,),
            "kicad_version": (source.source_file.kicad_version,),
            "rule_name": (source.rule_name,),
            "rule_ordinal": (str(source.rule_ordinal),),
            "layer_names": tuple(issue.layer_name for issue in source.issues),
            "issue_kinds": tuple(issue.kind for issue in source.issues),
            "locations": tuple(issue.location for issue in source.issues),
            "canonical_layers": tuple(issue.canonical_layer or "" for issue in source.issues),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDruLayerCandidate(Candidate):
    """Review prompt for a noncanonical or unmatched custom-rule layer."""

    source_evidence: PcbDruLayerFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDruLayerFindingEvidence,
        *,
        message: str,
    ) -> PcbDruLayerCandidate:
        projection = project_pcb_dru_layer_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.source_file.source_path}#rule"
                f"[{source_evidence.rule_ordinal}] {source_evidence.rule_name}"
            ),
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_dru_layer_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Custom DRC layer fields must match their source-bound projection")
