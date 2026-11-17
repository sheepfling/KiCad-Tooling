"""Compatibility entry point for component-pad Excellon drill binding."""

from __future__ import annotations

from .fabrication_contact_source import SourceComponentPad
from .fabrication_drill_binding import require_excellon_source_drills
from .fabrication_excellon import DrillHit


def require_excellon_source_pad_drills(
    source_pads: tuple[SourceComponentPad, ...],
    plated_drills: tuple[DrillHit, ...],
    nonplated_drills: tuple[DrillHit, ...],
) -> None:
    """Require unique plating-correct Excellon hits for drilled component pads."""
    require_excellon_source_drills(source_pads, (), plated_drills, nonplated_drills)
