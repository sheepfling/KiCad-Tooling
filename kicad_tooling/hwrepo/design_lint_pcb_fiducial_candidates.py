"""Candidate translation for authored fiducial-count coverage."""

from __future__ import annotations

from .design_lint_pcb_fiducial_candidate_evidence import (
    PcbFiducialCandidate,
    PcbFiducialFindingEvidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def pcb_fiducial_candidates(
    inventory: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Turn configured fiducial shortfalls and blocked scans into review findings."""
    if inventory is None:
        return ()
    report = inventory.fiducial_coverage
    if report.status == "BLOCKED":
        return (
            PcbFiducialCandidate.from_source_evidence(
                PcbFiducialFindingEvidence(report=report),
                subject="native PCB fiducial inventory unavailable",
                message=(
                    "The configured board-level fiducial requirement could not be compared with "
                    "source-bound native PCB evidence. No conclusion about its count is available."
                ),
            ),
        )
    if report.status != "INCOMPLETE":
        return ()
    return tuple(
        PcbFiducialCandidate.from_source_evidence(
            PcbFiducialFindingEvidence(report=report, entry=entry),
            subject=f"{entry.id}: board fiducials on {entry.side} side",
            message=(
                f"The native board contains {entry.observed_count} fitted footprint(s) matching "
                f"the authored fiducial identities; {entry.minimum_count} are required. Review "
                "the project requirement and board placements. This check does not count panel "
                "fiducials or establish assembly-vision or manufacturing suitability."
            ),
        )
        for entry in report.entries
        if entry.status == "INCOMPLETE"
    )
