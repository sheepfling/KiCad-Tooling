"""Source-bound checks for circular plated through-contact land flashes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .fabrication_artwork import GerberFeature, GerberLayer
from .fabrication_contact_source import SourceComponentPad
from .fabrication_via_binding import SourceVia

if TYPE_CHECKING:
    from .fabrication_connectivity_raster import PadAssignment

_NM_PER_MM = 1_000_000
_GERBER_INCH_QUANTIZATION_TOLERANCE_NM = 13
_BUCKET_NM = 26


@dataclass(frozen=True, slots=True)
class CircularLandRequirement:
    """A source-mapped circular plated contact land expected on every copper layer."""

    contact: str
    net: str | None
    x_nm: int
    y_nm: int
    diameter_nm: int


@dataclass(frozen=True, slots=True)
class MissingCircularLandFlashes:
    """One source contact whose expected circular flash is absent on some layers."""

    requirement: CircularLandRequirement
    layers: tuple[str, ...]


def circular_land_requirements(
    source_pads: tuple[SourceComponentPad, ...], source_vias: tuple[SourceVia, ...]
) -> tuple[CircularLandRequirement, ...]:
    """Select only circular, full-stack plated source pads and ordinary vias."""
    requirements = [
        CircularLandRequirement(
            contact=f"{pad.reference}-{pad.number}",
            net=pad.net_name,
            x_nm=pad.x_nm,
            y_nm=-pad.y_nm,
            diameter_nm=pad.size_x_nm,
        )
        for pad in source_pads
        if pad.contact_layer == "through"
        and pad.drill_plating == "plated"
        and pad.pad_shape == "circle"
        and not pad.has_custom_padstack
        and pad.size_x_nm is not None
        and pad.size_x_nm == pad.size_y_nm
    ]
    requirements.extend(
        CircularLandRequirement(
            contact="VIA-via",
            net=via.net_name,
            x_nm=via.x_nm,
            y_nm=-via.y_nm,
            diameter_nm=via.copper_diameter_nm,
        )
        for via in source_vias
        if via.copper_diameter_nm is not None
    )
    return tuple(
        sorted(
            requirements,
            key=lambda item: (
                item.contact.casefold(),
                item.net or "",
                item.x_nm,
                item.y_nm,
                item.diameter_nm,
            ),
        )
    )


def missing_circular_land_flashes(
    layers: tuple[GerberLayer, ...],
    requirements: tuple[CircularLandRequirement, ...],
) -> tuple[MissingCircularLandFlashes, ...]:
    """Find source-sized D03 circle flashes missing from any source copper layer.

    The accepted Gerber coordinate format has six decimal places. This allows
    half of one six-decimal inch unit (12.7 nm), rounded up, when matching
    coordinates and aperture diameters to integer-nanometer source geometry.
    """
    unmatched: list[tuple[CircularLandRequirement, list[str]]] = [
        (requirement, []) for requirement in requirements
    ]
    for layer in layers:
        available = _circle_flash_index(layer.features)
        for requirement, missing in unmatched:
            match = _take_matching_flash(available, requirement)
            if match is None:
                missing.append(layer.layer)
    return tuple(
        MissingCircularLandFlashes(requirement, tuple(missing))
        for requirement, missing in unmatched
        if missing
    )


def raster_visible_missing_layers(
    missing: MissingCircularLandFlashes,
    assignments: tuple[PadAssignment, ...],
) -> tuple[str, ...]:
    """Keep the new finding only where raster copper presence would mask it.

    A completely absent contact-layer land remains covered by the existing
    per-layer copper finding. This rule adds a finding where some non-flash
    copper makes the raster consider the source contact present.
    """
    requirement = missing.requirement
    matches: list[PadAssignment] = []
    for assignment in assignments:
        contact = assignment.contact
        if contact.label != requirement.contact:
            continue
        if requirement.net is not None and contact.net != requirement.net:
            continue
        if requirement.net is None and not contact.net.startswith("N/C:"):
            continue
        tolerance_nm = contact.coordinate_resolution_nm // 2 + 1
        observed = (round(contact.x_mm * _NM_PER_MM), round(contact.y_mm * _NM_PER_MM))
        expected = (requirement.x_nm, requirement.y_nm)
        if all(abs(left - right) <= tolerance_nm for left, right in zip(observed, expected)):
            matches.append(assignment)
    if not matches:
        return missing.layers
    if not any(assignment.components for assignment in matches):
        return ()
    raster_present: set[str] = {
        layer
        for assignment in matches
        if assignment.components
        for layer in missing.layers
        if layer not in assignment.missing_layers
    }
    return tuple(layer for layer in missing.layers if layer in raster_present)


def _bucket(value_nm: int) -> int:
    return round(value_nm / _BUCKET_NM)


def _circle_flash_index(
    features: tuple[GerberFeature, ...],
) -> dict[tuple[int, int, int], list[tuple[int, int, int]]]:
    index: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for feature in features:
        if (
            feature.kind != "flash"
            or feature.aperture is None
            or feature.aperture[0] != "C"
            or len(feature.aperture[1]) != 1
            or len(feature.points) != 1
        ):
            continue
        x_mm, y_mm = feature.points[0]
        diameter_mm = feature.aperture[1][0]
        point = (
            round(x_mm * _NM_PER_MM),
            round(y_mm * _NM_PER_MM),
            round(diameter_mm * _NM_PER_MM),
        )
        key = (_bucket(point[0]), _bucket(point[1]), _bucket(point[2]))
        index.setdefault(key, []).append(point)
    for points in index.values():
        points.sort()
    return index


def _take_matching_flash(
    available: dict[tuple[int, int, int], list[tuple[int, int, int]]],
    requirement: CircularLandRequirement,
) -> tuple[int, int, int] | None:
    tolerance = _GERBER_INCH_QUANTIZATION_TOLERANCE_NM
    expected = (requirement.x_nm, requirement.y_nm, requirement.diameter_nm)
    center = tuple(_bucket(value) for value in expected)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dd in (-1, 0, 1):
                key = (center[0] + dx, center[1] + dy, center[2] + dd)
                candidates = available.get(key, [])
                for index, candidate in enumerate(candidates):
                    if all(
                        abs(left - right) <= tolerance for left, right in zip(candidate, expected)
                    ):
                        return candidates.pop(index)
    return None
