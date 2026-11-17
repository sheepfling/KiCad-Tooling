"""Bind source PCB via drill geometry to exported plated Excellon hits."""

from __future__ import annotations

from .fabrication_artwork import UnsupportedFabricationFormat
from .fabrication_excellon import DrillHit
from .fabrication_via_binding import SourceVia

_NM_PER_MM = 1_000_000


def require_excellon_source_via_drills(
    source_vias: tuple[SourceVia, ...], plated_drills: tuple[DrillHit, ...]
) -> None:
    """Require every source via's center and drill size in the plated drill output."""
    circular_hits = tuple(hit for hit in plated_drills if hit.end_mm is None)
    for via in source_vias:
        center_hits = tuple(
            hit
            for hit in circular_hits
            if abs(round(hit.x_mm * _NM_PER_MM) - via.x_nm) <= hit.coordinate_resolution_nm // 2 + 1
            and abs(round(hit.y_mm * _NM_PER_MM) + via.y_nm)
            <= hit.coordinate_resolution_nm // 2 + 1
        )
        matching_hits = tuple(
            hit
            for hit in center_hits
            if abs(round(hit.diameter_mm * _NM_PER_MM) - via.drill_nm)
            <= hit.diameter_resolution_nm // 2 + 1
        )
        if matching_hits:
            continue
        if center_hits:
            observed_diameters = ", ".join(
                f"{hit.diameter_mm:g} mm"
                for hit in sorted(center_hits, key=lambda item: item.diameter_mm)
            )
            raise UnsupportedFabricationFormat(
                f"plated Excellon drill diameter at source via "
                f"({via.x_nm} nm, {via.y_nm} nm) differs from source PCB "
                f"({observed_diameters}; expected {via.drill_nm} nm)"
            )
        raise UnsupportedFabricationFormat(
            f"plated Excellon has no circular drill hit at source via "
            f"({via.x_nm} nm, {via.y_nm} nm) with diameter {via.drill_nm} nm"
        )
