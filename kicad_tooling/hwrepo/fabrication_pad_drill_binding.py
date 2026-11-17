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
        if pad.drill_shape not in {"circular", "oval"} or pad.drill_nm is None:
            raise UnsupportedFabricationFormat(
                f"source drilled pad {pad.reference}.{pad.number} has an unsupported drill shape"
            )
        output = plated_drills if pad.drill_plating == "plated" else nonplated_drills
        hit_offset = 0 if pad.drill_plating == "plated" else len(plated_drills)
        located = tuple(
            (index, hit) for index, hit in enumerate(output) if _center_matches(pad, hit)
        )
        matches = tuple(
            index + hit_offset for index, hit in located if _drill_geometry_matches(pad, hit)
        )
        if not matches:
            plating = pad.drill_plating
            if located and pad.drill_shape == "circular":
                observed = ", ".join(
                    f"{hit.diameter_mm:g} mm"
                    for _, hit in sorted(located, key=lambda item: item[1].diameter_mm)
                    if hit.end_mm is None
                )
                if observed:
                    raise UnsupportedFabricationFormat(
                        f"{plating} Excellon drill diameter at source pad "
                        f"{pad.reference}.{pad.number} differs from source PCB "
                        f"({observed}; expected {pad.drill_nm} nm)"
                    )
            if located and pad.drill_shape == "oval":
                raise UnsupportedFabricationFormat(
                    f"{plating} Excellon slot geometry at source pad "
                    f"{pad.reference}.{pad.number} differs from source PCB"
                )
            raise UnsupportedFabricationFormat(
                f"{plating} Excellon has no {pad.drill_shape} drill hit at source pad "
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
    hit_x_mm = hit.x_mm
    hit_y_mm = hit.y_mm
    if hit.end_mm is not None:
        hit_x_mm = (hit.x_mm + hit.end_mm[0]) / 2
        hit_y_mm = (hit.y_mm + hit.end_mm[1]) / 2
    return (
        abs(round(hit_x_mm * _NM_PER_MM) - pad.x_nm) <= tolerance
        and abs(round(hit_y_mm * _NM_PER_MM) + pad.y_nm) <= tolerance
    )


def _drill_geometry_matches(pad: SourceComponentPad, hit: DrillHit) -> bool:
    assert pad.drill_nm is not None
    diameter_tolerance = hit.diameter_resolution_nm // 2 + 1
    if abs(round(hit.diameter_mm * _NM_PER_MM) - pad.drill_nm) > diameter_tolerance:
        return False
    if pad.drill_shape == "circular":
        return hit.end_mm is None
    if hit.end_mm is None or pad.drill_width_nm is None or pad.drill_height_nm is None:
        return False

    coordinate_tolerance = hit.coordinate_resolution_nm + 2
    delta_x_nm = round(abs(hit.end_mm[0] - hit.x_mm) * _NM_PER_MM)
    delta_y_nm = round(abs(hit.end_mm[1] - hit.y_mm) * _NM_PER_MM)
    expected_x_nm = abs(pad.drill_width_nm - pad.drill_height_nm)
    expected_y_nm = 0
    if pad.drill_height_nm > pad.drill_width_nm:
        expected_x_nm, expected_y_nm = 0, expected_x_nm
    return (
        abs(delta_x_nm - expected_x_nm) <= coordinate_tolerance
        and abs(delta_y_nm - expected_y_nm) <= coordinate_tolerance
    )
