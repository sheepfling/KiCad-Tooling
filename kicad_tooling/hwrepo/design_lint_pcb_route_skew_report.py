"""Text rendering for measured differential-pair route-skew evidence."""

from __future__ import annotations

from .pcb_differential_pair_skew_models import PcbDifferentialPairRouteSkewReport


def pcb_route_skew_report_lines(
    report: PcbDifferentialPairRouteSkewReport | None,
) -> list[str]:
    """Render explicit route lengths, thresholds, and source binding."""
    if report is None or report.status == "NOT_REQUESTED":
        return []
    lines = [
        (
            "PCB differential-pair routed skew: "
            f"{report.status} (mode: {report.mode or 'not configured'})"
        )
    ]
    if report.board_path is not None:
        lines.append(
            f"  Board: {report.board_path} (SHA-256 {report.board_sha256 or 'unavailable'})"
        )
    if report.snapshot_path is not None:
        lines.append(
            f"  Native snapshot: {report.snapshot_path} "
            f"(SHA-256 {report.snapshot_sha256 or 'unavailable'})"
        )
    for entry in report.entries:
        skew = "unavailable" if entry.measured_skew_nm is None else f"{entry.measured_skew_nm} nm"
        lines.append(
            f"  {entry.bundle_id}: {entry.status}; measured skew {skew}; "
            f"maximum {entry.max_skew_nm} nm"
        )
        for path in entry.paths:
            length = "unavailable" if path.length_nm is None else f"{path.length_nm} nm"
            lines.append(
                f"    {path.path_id}: {path.net} {path.from_pad} to {path.to_pad}; "
                f"{path.status}; length {length}; tracks {', '.join(path.track_uuids) or 'none'}"
            )
            if path.issue is not None:
                lines.append(f"      Coverage issue: {path.issue}")
        if entry.issue is not None:
            lines.append(f"    Coverage issue: {entry.issue}")
    if report.issue is not None:
        lines.append(f"  Coverage issue: {report.issue}")
    return lines
