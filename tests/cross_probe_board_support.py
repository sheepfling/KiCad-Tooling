"""Small source-bound PCB marker records shared by cross-probe regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.cross_probe_board import (
    BoardFootprintAnchorsByCasefoldedReference,
    BoardMarkerDrawingStatus,
    CrossProbeBoardMarkerResolution,
)
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing


def source_bound_board_marker_resolution(
    *,
    board_path: str,
    board_source_sha256: str | None,
    anchors: BoardFootprintAnchorsByCasefoldedReference | None = None,
    findings_view_path: str = "build/findings/review.json",
    findings_view_sha256: str = "f" * 64,
    drawings: tuple[ReviewDrawing, ...] = (),
) -> CrossProbeBoardMarkerResolution:
    """Construct structurally valid marker evidence for reconciliation tests."""
    pcb_drawings = tuple(drawing for drawing in drawings if drawing.kind == "pcb")
    if not pcb_drawings:
        drawing_status: BoardMarkerDrawingStatus = "UNAVAILABLE"
        board_drawing = None
    elif len(pcb_drawings) > 1:
        drawing_status = "AMBIGUOUS"
        board_drawing = None
    else:
        board_drawing = pcb_drawings[0]
        drawing_status = "UNIQUE" if board_drawing.mapping_supported else "UNSUPPORTED"
    blocked = board_source_sha256 is None
    return CrossProbeBoardMarkerResolution(
        board_path=board_path,
        board_source_sha256=board_source_sha256,
        board_status="BLOCKED" if blocked else "COMPLETE",
        anchors_by_casefolded_reference=anchors or {},
        findings_view_path=findings_view_path,
        findings_view_sha256=findings_view_sha256,
        drawing_candidates=pcb_drawings,
        drawing_status=drawing_status,
        board_drawing=board_drawing,
        issues=("PCB source is unavailable.",) if blocked else (),
    )
