"""Review prompts for PCB footprint references absent from the schematic."""

from __future__ import annotations

from .design_lint_pcb_board_only_candidate_evidence import (
    PcbBlockedBoardOnlyFootprintCandidate,
    PcbBlockedBoardOnlyFootprintEvidence,
    PcbBoardOnlyFootprintCandidate,
    PcbBoardOnlyFootprintEvidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)


def pcb_board_only_footprint_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate board-only coverage into source-bound review candidates."""
    if report is None:
        return ()
    coverage = report.board_only_footprint_coverage
    if coverage.status == "DISABLED":
        return ()
    if coverage.status == "BLOCKED":
        return (
            PcbBlockedBoardOnlyFootprintCandidate.from_source_evidence(
                PcbBlockedBoardOnlyFootprintEvidence(report),
                subject="native schematic-to-PCB reference comparison unavailable",
                message=(
                    "The source-bound schematic and native PCB footprint references could not be "
                    "compared. No conclusion about board-only footprints is available."
                ),
            ),
        )

    receipt = PcbComponentInventorySourceReceipt.from_coverage_report(report)
    return tuple(
        PcbBoardOnlyFootprintCandidate.from_source_evidence(
            PcbBoardOnlyFootprintEvidence(observation=item, receipt=receipt),
            subject=f"{item.reference}: PCB footprint has no schematic counterpart",
            message=(
                "This native PCB footprint reference is absent from the source-bound schematic. "
                "It may be an intentional mechanical, fabrication, or board-only item; confirm "
                "that it is deliberate or add its schematic counterpart. This comparison does "
                "not infer electrical role, assembly state, or manufacturing intent."
            ),
        )
        for item in coverage.footprints
    )
