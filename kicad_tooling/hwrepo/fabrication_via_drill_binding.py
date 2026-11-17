"""Compatibility entry point for source PCB via drill binding."""

from __future__ import annotations

from .fabrication_drill_binding import require_excellon_source_drills
from .fabrication_excellon import DrillHit
from .fabrication_via_binding import SourceVia


def require_excellon_source_via_drills(
    source_vias: tuple[SourceVia, ...], plated_drills: tuple[DrillHit, ...]
) -> None:
    """Require unique full-stack Excellon hits for source PCB vias."""
    require_excellon_source_drills((), source_vias, plated_drills, ())
