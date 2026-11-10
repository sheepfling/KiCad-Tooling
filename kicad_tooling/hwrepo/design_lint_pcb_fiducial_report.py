"""Render source-bound board fiducial coverage for human lint reports."""

from __future__ import annotations

from .pcb_fiducial_models import PcbFiducialCoverageReport


def pcb_fiducial_report_lines(coverage: PcbFiducialCoverageReport) -> list[str]:
    """Show authored requirements, exact native matches, and evidence identity."""
    if coverage.status == "NOT_REQUESTED":
        return []
    lines = [
        (
            f"PCB board fiducial coverage: {coverage.status} "
            f"(mode: {coverage.mode or 'not configured'}; board footprints only)"
        )
    ]
    if coverage.board_path is not None:
        lines.append(
            f"  Board: {coverage.board_path} (SHA-256 {coverage.board_sha256 or 'unavailable'})"
        )
    if coverage.snapshot_path is not None:
        lines.append(
            f"  Native footprint snapshot: {coverage.snapshot_path} "
            f"(SHA-256 {coverage.snapshot_sha256 or 'unavailable'}; "
            f"schema {coverage.snapshot_schema or 'unknown'}; "
            f"KiCad {coverage.kicad_version or 'unknown'})"
        )
    if coverage.map_sha256 is not None:
        lines.append(f"  Requirement map SHA-256: {coverage.map_sha256}")
    for entry in coverage.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.observed_count} fitted match(es); "
            f"{entry.minimum_count} required on {entry.side}; "
            f"accepted: {', '.join(entry.accepted_footprints)}"
        )
        for item in entry.observations:
            x_nm, y_nm = item.position_nm
            lines.append(
                f"    {item.reference}: {item.footprint}; {item.side}; position {x_nm},{y_nm} nm"
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if coverage.issue is not None:
        lines.append(f"  Coverage issue: {coverage.issue}")
    lines.append(
        "  This check counts exact authored footprint identities on the board; "
        "it does not verify panel fiducials, pad geometry, vision performance, or suitability."
    )
    return lines
