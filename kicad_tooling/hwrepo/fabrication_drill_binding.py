"""Bind every source PCB drill feature to a unique Excellon hit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .fabrication_artwork import UnsupportedFabricationFormat
from .fabrication_contact_source import SourceComponentPad
from .fabrication_excellon import DrillHit
from .fabrication_via_binding import SourceVia

_NM_PER_MM = 1_000_000


@dataclass(frozen=True, slots=True)
class SourceDrillRequirement:
    """One component-pad or via drill that must own an artifact hit."""

    source_kind: Literal["pad", "via"]
    source_identity: str
    plating: Literal["plated", "nonplated"]
    x_nm: int
    y_nm: int
    shape: Literal["circular", "oval"]
    diameter_nm: int
    width_nm: int
    height_nm: int


@dataclass(frozen=True, slots=True)
class UnboundDrillHit:
    """One exported drill hit not owned by a source pad or via."""

    plating: Literal["plated", "nonplated"]
    hit: DrillHit


def source_drill_requirements(
    source_pads: tuple[SourceComponentPad, ...],
    source_vias: tuple[SourceVia, ...],
) -> tuple[SourceDrillRequirement, ...]:
    """Combine source pad and via drills into one stable matching inventory."""
    requirements: list[SourceDrillRequirement] = []
    for pad in source_pads:
        if pad.drill_plating is None:
            continue
        if (pad.drill_shape != "circular" and pad.drill_shape != "oval") or pad.drill_nm is None:
            raise UnsupportedFabricationFormat(
                f"source drilled pad {pad.reference}.{pad.number} has an unsupported drill shape"
            )
        width_nm = pad.drill_width_nm
        height_nm = pad.drill_height_nm
        if pad.drill_shape == "circular":
            width_nm = width_nm if width_nm is not None else pad.drill_nm
            height_nm = height_nm if height_nm is not None else pad.drill_nm
        if width_nm is None or height_nm is None:
            raise UnsupportedFabricationFormat(
                f"source drilled pad {pad.reference}.{pad.number} has incomplete drill geometry"
            )
        requirements.append(
            SourceDrillRequirement(
                source_kind="pad",
                source_identity=f"source pad {pad.reference}.{pad.number}",
                plating=pad.drill_plating,
                x_nm=pad.x_nm,
                y_nm=pad.y_nm,
                shape=pad.drill_shape,
                diameter_nm=pad.drill_nm,
                width_nm=width_nm,
                height_nm=height_nm,
            )
        )
    for via in source_vias:
        requirements.append(
            SourceDrillRequirement(
                source_kind="via",
                source_identity=(f"source via on {via.net_name} at ({via.x_nm} nm, {via.y_nm} nm)"),
                plating="plated",
                x_nm=via.x_nm,
                y_nm=via.y_nm,
                shape="circular",
                diameter_nm=via.drill_nm,
                width_nm=via.drill_nm,
                height_nm=via.drill_nm,
            )
        )
    return tuple(
        sorted(
            requirements,
            key=lambda item: (
                item.plating,
                item.source_identity.casefold(),
                item.source_identity,
            ),
        )
    )


def require_excellon_source_drills(
    source_pads: tuple[SourceComponentPad, ...],
    source_vias: tuple[SourceVia, ...],
    plated_drills: tuple[DrillHit, ...],
    nonplated_drills: tuple[DrillHit, ...],
) -> tuple[UnboundDrillHit, ...]:
    """Require unique source-hit ownership and return artifact-only drill hits."""
    requirements = source_drill_requirements(source_pads, source_vias)
    unmatched: list[UnboundDrillHit] = []
    drill_sets: tuple[tuple[Literal["plated", "nonplated"], tuple[DrillHit, ...]], ...] = (
        ("plated", plated_drills),
        ("nonplated", nonplated_drills),
    )
    for plating, hits in drill_sets:
        scoped = tuple(item for item in requirements if item.plating == plating)
        assigned = _require_unique_hit_assignment(scoped, hits, plating)
        unmatched.extend(
            UnboundDrillHit(plating=plating, hit=hit)
            for index, hit in enumerate(hits)
            if index not in assigned
        )
    return tuple(unmatched)


def _require_unique_hit_assignment(
    requirements: tuple[SourceDrillRequirement, ...],
    hits: tuple[DrillHit, ...],
    plating: str,
) -> frozenset[int]:
    if not requirements:
        return frozenset()

    candidates_by_requirement: list[tuple[int, ...]] = []
    for requirement in requirements:
        centered = tuple(
            (index, hit) for index, hit in enumerate(hits) if _center_matches(requirement, hit)
        )
        candidates = tuple(index for index, hit in centered if _geometry_matches(requirement, hit))
        if not candidates:
            _raise_unmatched_requirement(requirement, centered, plating)
        candidates_by_requirement.append(candidates)

    owners_by_hit: dict[int, int] = {}

    def assign(requirement_index: int, seen: set[int]) -> bool:
        for hit_index in candidates_by_requirement[requirement_index]:
            if hit_index in seen:
                continue
            seen.add(hit_index)
            owner = owners_by_hit.get(hit_index)
            if owner is None or assign(owner, seen):
                owners_by_hit[hit_index] = requirement_index
                return True
        return False

    for requirement_index in sorted(
        range(len(requirements)),
        key=lambda index: (
            len(candidates_by_requirement[index]),
            requirements[index].source_identity.casefold(),
            requirements[index].source_identity,
        ),
    ):
        if assign(requirement_index, set()):
            continue
        requirement = requirements[requirement_index]
        raise UnsupportedFabricationFormat(
            "Excellon drill hits cannot uniquely bind all source PCB pads and vias; "
            f"no independent hit remains for {requirement.source_identity}"
        )
    return frozenset(owners_by_hit)


def _center_matches(requirement: SourceDrillRequirement, hit: DrillHit) -> bool:
    x_mm = hit.x_mm
    y_mm = hit.y_mm
    if hit.end_mm is not None:
        x_mm = (hit.x_mm + hit.end_mm[0]) / 2
        y_mm = (hit.y_mm + hit.end_mm[1]) / 2
    tolerance = hit.coordinate_resolution_nm // 2 + 1
    return (
        abs(round(x_mm * _NM_PER_MM) - requirement.x_nm) <= tolerance
        and abs(round(y_mm * _NM_PER_MM) + requirement.y_nm) <= tolerance
    )


def _geometry_matches(requirement: SourceDrillRequirement, hit: DrillHit) -> bool:
    diameter_tolerance = hit.diameter_resolution_nm // 2 + 1
    if abs(round(hit.diameter_mm * _NM_PER_MM) - requirement.diameter_nm) > diameter_tolerance:
        return False
    if requirement.shape == "circular":
        return hit.end_mm is None
    if hit.end_mm is None:
        return False

    coordinate_tolerance = hit.coordinate_resolution_nm + 2
    delta_x_nm = round(abs(hit.end_mm[0] - hit.x_mm) * _NM_PER_MM)
    delta_y_nm = round(abs(hit.end_mm[1] - hit.y_mm) * _NM_PER_MM)
    expected_x_nm = abs(requirement.width_nm - requirement.height_nm)
    expected_y_nm = 0
    if requirement.height_nm > requirement.width_nm:
        expected_x_nm, expected_y_nm = 0, expected_x_nm
    return (
        abs(delta_x_nm - expected_x_nm) <= coordinate_tolerance
        and abs(delta_y_nm - expected_y_nm) <= coordinate_tolerance
    )


def _raise_unmatched_requirement(
    requirement: SourceDrillRequirement,
    centered: tuple[tuple[int, DrillHit], ...],
    plating: str,
) -> None:
    if requirement.source_kind == "via":
        circular = tuple(hit for _, hit in centered if hit.end_mm is None)
        if circular:
            observed = ", ".join(
                f"{hit.diameter_mm:g} mm"
                for hit in sorted(circular, key=lambda item: item.diameter_mm)
            )
            raise UnsupportedFabricationFormat(
                f"plated Excellon drill diameter at {requirement.source_identity} differs "
                f"from source PCB ({observed}; expected {requirement.diameter_nm} nm)"
            )
        raise UnsupportedFabricationFormat(
            f"plated Excellon has no circular drill hit at {requirement.source_identity} "
            f"with diameter {requirement.diameter_nm} nm"
        )

    if centered and requirement.shape == "oval":
        raise UnsupportedFabricationFormat(
            f"{plating} Excellon slot geometry at {requirement.source_identity} differs "
            "from source PCB"
        )
    if centered and requirement.shape == "circular":
        observed = ", ".join(
            f"{hit.diameter_mm:g} mm"
            for _, hit in sorted(centered, key=lambda item: item[1].diameter_mm)
            if hit.end_mm is None
        )
        if observed:
            raise UnsupportedFabricationFormat(
                f"{plating} Excellon drill diameter at {requirement.source_identity} differs "
                f"from source PCB ({observed}; expected {requirement.diameter_nm} nm)"
            )
    raise UnsupportedFabricationFormat(
        f"{plating} Excellon has no {requirement.shape} drill hit at "
        f"{requirement.source_identity} ({requirement.x_nm} nm, {requirement.y_nm} nm)"
    )
