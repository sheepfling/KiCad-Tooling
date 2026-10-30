"""Verify retained findings drawings before sharing them in other views."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .artifact_access import artifact_file, read_regular_bytes
from .findings_view_models import FindingsViewReport, ReviewDrawing
from .findings_view_svg import prepare_drawing


def verified_findings_drawing(
    root: Path, report_path: Path, drawing: ReviewDrawing, report: FindingsViewReport
) -> bytes:
    """Read one exact, passive SVG matching its receipt and drawing metadata."""
    name = drawing.file
    if PurePosixPath(name).name != name or not name.endswith(".svg"):
        raise ValueError("Findings drawing has an unsafe filename")
    path = artifact_file(root, (report_path.parent / name).relative_to(root).as_posix())
    content, _ = read_regular_bytes(path, maximum=32 * 1024 * 1024)
    if (
        hashlib.sha256(content).hexdigest() != drawing.sha256
        or report.artifacts_sha256.get(name) != drawing.sha256
    ):
        raise ValueError(f"Retained findings drawing changed: {name}")
    inspected = prepare_drawing(content, drawing.kind)
    if (
        inspected.content != content
        or inspected.width != drawing.width_mm
        or inspected.height != drawing.height_mm
        or (drawing.mapping_supported and not inspected.can_map_mm)
    ):
        raise ValueError(f"Retained findings drawing metadata differs: {name}")
    return content
