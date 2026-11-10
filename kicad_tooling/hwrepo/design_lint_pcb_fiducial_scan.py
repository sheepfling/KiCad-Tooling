"""Blocked and disabled PCB fiducial evidence states."""

from __future__ import annotations

from .design_lint_pcb_coverage_common import PcbRuleMode, map_sha256
from .model_primitives import Digest, RepositoryPath
from .pcb_board_source_binding import pcb_board_source_matches
from .pcb_fiducial_models import (
    PcbFiducialCoverageReport,
    PcbFiducialMap,
)
from .source_state_models import SourceHashInventory


def blocked_pcb_fiducial_coverage(
    requirements: PcbFiducialMap | None,
    mode: PcbRuleMode,
    board_path: RepositoryPath,
    issue: str,
) -> PcbFiducialCoverageReport:
    """Preserve unavailable native source as blocked coverage, never as a pass."""
    if requirements is None:
        return PcbFiducialCoverageReport()
    if mode == "off":
        return PcbFiducialCoverageReport(status="DISABLED", mode=mode)
    return PcbFiducialCoverageReport(
        status="BLOCKED",
        mode=mode,
        map_sha256=map_sha256(requirements),
        board_path=board_path,
        issue=issue,
    )


def normalize_pcb_fiducial_coverage(
    coverage: PcbFiducialCoverageReport,
    requirements: PcbFiducialMap | None,
    mode: PcbRuleMode,
    *,
    source_hashes: SourceHashInventory,
    netlist_sha256: Digest | None,
) -> PcbFiducialCoverageReport:
    """Reject missing, stale-map, stale-board, or stale-netlist fiducial evidence."""
    if requirements is None:
        return PcbFiducialCoverageReport()
    if mode == "off":
        return PcbFiducialCoverageReport(status="DISABLED", mode=mode)
    map_digest = map_sha256(requirements)
    if coverage.status not in {"COMPLETE", "INCOMPLETE"}:
        return PcbFiducialCoverageReport(
            status="BLOCKED",
            mode=mode,
            map_sha256=map_digest,
            issue="Source-bound native PCB footprint evidence was not supplied for the fiducial map",
        )
    if coverage.map_sha256 != map_digest:
        issue = "Fiducial coverage does not bind the current project-authored requirement map"
    elif not pcb_board_source_matches(coverage.board_path, coverage.board_sha256, source_hashes):
        issue = "Fiducial coverage differs from the current native PCB source"
    elif netlist_sha256 is None or coverage.netlist_sha256 != netlist_sha256:
        issue = "Fiducial coverage uses a different source-bound native netlist"
    else:
        return coverage.model_copy(update={"mode": mode})
    return PcbFiducialCoverageReport(
        status="BLOCKED",
        mode=mode,
        map_sha256=map_digest,
        issue=issue,
    )
