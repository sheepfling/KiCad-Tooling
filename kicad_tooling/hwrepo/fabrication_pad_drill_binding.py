"""Bind source drilled component pads to the exported Excellon drill files."""

from __future__ import annotations

from .fabrication_artwork import UnsupportedFabricationFormat
from .fabrication_contact_source import SourceComponentPad
from .fabrication_excellon import DrillHit

_NM_PER_MM = 1_000_000


def require_excellon_source_pad_drills(
    source_pads: tuple[SourceComponentPad, ...],
    plated_drills: tuple[DrillHit, ...],
    nonplated_drills: tuple[DrillHit, ...],
) -> None:
    """Require each supported source pad hole in its matching plating class."""
    drilled = tuple(pad for pad in source_pads if pad.drill_plating is not None)
    if not drilled:
        return

    candidates_by_pad: list[tuple[int, ...]] = []
    for pad in drilled:
        if pad.drill_shape != "circular" or pad.drill_nm is None:
            raise UnsupportedFabricationFormat(
                f"source drilled pad {pad.reference}.{pad.number} has an unsupported drill shape"
            )
        output = plated_drills if pad.drill_plating == "plated" else nonplated_drills
        hit_offset = 0 if pad.drill_plating == "plated" else len(plated_drills)
        circular = tuple((index, hit) for index, hit in enumerate(output) if hit.end_mm is None)
        centered = tuple((index, hit) for index, hit in circular if _center_matches(pad, hit))
        matches = tuple(
            index + hit_offset for index, hit in centered if _diameter_matches(pad, hit)
        )
        if not matches:
            plating = pad.drill_plating
            if centered:
                observed = ", ".join(
                    f"{hit.diameter_mm:g} mm"
                    for _, hit in sorted(centered, key=lambda item: item[1].diameter_mm)
                )
                raise UnsupportedFabricationFormat(
                    f"{plating} Excellon drill diameter at source pad "
                    f"{pad.reference}.{pad.number} differs from source PCB "
                    f"({observed}; expected {pad.drill_nm} nm)"
                )
            raise UnsupportedFabricationFormat(
                f"{plating} Excellon has no circular drill hit at source pad "
                f"{pad.reference}.{pad.number} ({pad.x_nm} nm, {pad.y_nm} nm)"
            )
        candidates_by_pad.append(matches)

    owners_by_hit: dict[int, int] = {}

    def assign(pad_index: int, seen: set[int]) -> bool:
        for hit_index in candidates_by_pad[pad_index]:
            if hit_index in seen:
                continue
            seen.add(hit_index)
            owner = owners_by_hit.get(hit_index)
            if owner is None or assign(owner, seen):
                owners_by_hit[hit_index] = pad_index
                return True
        return False

    for pad_index in sorted(range(len(drilled)), key=lambda index: len(candidates_by_pad[index])):
        if assign(pad_index, set()):
            continue
        pad = drilled[pad_index]
        raise UnsupportedFabricationFormat(
            "Excellon drill hits cannot uniquely bind all source PCB drilled pads; "
            f"no independent hit remains for {pad.reference}.{pad.number}"
        )


def _center_matches(pad: SourceComponentPad, hit: DrillHit) -> bool:
    tolerance = hit.coordinate_resolution_nm // 2 + 1
    return (
        abs(round(hit.x_mm * _NM_PER_MM) - pad.x_nm) <= tolerance
        and abs(round(hit.y_mm * _NM_PER_MM) + pad.y_nm) <= tolerance
    )


def _diameter_matches(pad: SourceComponentPad, hit: DrillHit) -> bool:
    assert pad.drill_nm is not None
    tolerance = hit.diameter_resolution_nm // 2 + 1
    return abs(round(hit.diameter_mm * _NM_PER_MM) - pad.drill_nm) <= tolerance
