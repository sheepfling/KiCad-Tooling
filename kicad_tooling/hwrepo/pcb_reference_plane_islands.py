"""Review candidates for mapped reference-zone islands without direct pad anchors."""

from __future__ import annotations

from .design_lint_pcb_reference_plane_island_candidate_evidence import (
    PcbReferencePlaneIslandCandidate,
    PcbReferencePlaneIslandFindingEvidence,
)
from .design_lint_types import Candidate
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport


def unanchored_reference_zone_island_candidates(
    report: PcbReferencePlaneCoverageReport,
) -> tuple[Candidate, ...]:
    """Review only islands selected by a project-authored reference-plane map."""
    if report.status not in {"COMPLETE", "INCOMPLETE"}:
        return ()
    return tuple(
        PcbReferencePlaneIslandCandidate.from_source_evidence(
            PcbReferencePlaneIslandFindingEvidence(
                report=report,
                entry=entry,
                island=island,
            )
        )
        for entry in report.entries
        if entry.review_unanchored_islands
        for island in entry.unanchored_reference_islands
    )
