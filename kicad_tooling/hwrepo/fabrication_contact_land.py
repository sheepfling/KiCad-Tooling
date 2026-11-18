"""Source-bound checks for standard component and via land flashes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .fabrication_artwork import GerberFeature, GerberLayer
from .fabrication_contact_source import SourceComponentPad
from .fabrication_via_binding import SourceVia

if TYPE_CHECKING:
    from .fabrication_connectivity_raster import PadAssignment

_NM_PER_MM = 1_000_000
_GERBER_INCH_QUANTIZATION_TOLERANCE_NM = 13
_BUCKET_NM = 26
_SourceLandShape = Literal["circle", "oval", "rect"]
_ApertureShape = Literal["C", "O", "R"]
_LandFlashKey = tuple[_ApertureShape, int, int, int, int]
_LandFlashPoint = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class SourceLandRequirement:
    """A source-mapped standard land expected on its assigned copper layer(s)."""

    contact: str
    net: str | None
    x_nm: int
    y_nm: int
    shape: _SourceLandShape
    size_x_nm: int
    size_y_nm: int
    contact_layer: Literal["top", "bottom", "through"] = "through"


@dataclass(frozen=True, slots=True)
class MissingSourceLandFlashes:
    """One source contact whose expected shaped flash is absent on some layers."""

    requirement: SourceLandRequirement
    layers: tuple[str, ...]


def source_land_requirements(
    source_pads: tuple[SourceComponentPad, ...], source_vias: tuple[SourceVia, ...]
) -> tuple[SourceLandRequirement, ...]:
    """Select supported circular, oval, and rectangular source lands.

    Gerber standard apertures preserve quarter-turn changes by swapping their
    dimensions. Other source rotations require a macro representation; the
    current parser reports those artifacts as unsupported instead of guessing.
    Surface-mount lands apply only to their outer copper layer; plated through
    pads and vias apply to the complete copper stack.
    """
    requirements: list[SourceLandRequirement] = []
    for pad in source_pads:
        shape = _source_land_shape(pad.pad_shape)
        if (
            pad.contact_layer not in {"top", "bottom", "through"}
            or (pad.contact_layer == "through" and pad.drill_plating != "plated")
            or shape is None
            or pad.has_custom_padstack
            or pad.size_x_nm is None
            or pad.size_y_nm is None
        ):
            continue
        size_x_nm, size_y_nm = pad.size_x_nm, pad.size_y_nm
        if shape == "circle":
            if size_x_nm != size_y_nm:
                continue
        elif pad.land_rotation_mdeg == 90_000:
            size_x_nm, size_y_nm = size_y_nm, size_x_nm
        elif pad.land_rotation_mdeg != 0:
            continue
        requirements.append(
            SourceLandRequirement(
                contact=f"{pad.reference}-{pad.number}",
                net=pad.net_name,
                x_nm=pad.x_nm,
                y_nm=-pad.y_nm,
                shape=shape,
                size_x_nm=size_x_nm,
                size_y_nm=size_y_nm,
                contact_layer=pad.contact_layer,
            )
        )
    requirements.extend(
        SourceLandRequirement(
            contact="VIA-via",
            net=via.net_name,
            x_nm=via.x_nm,
            y_nm=-via.y_nm,
            shape="circle",
            size_x_nm=via.copper_diameter_nm,
            size_y_nm=via.copper_diameter_nm,
            contact_layer="through",
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
                item.contact_layer,
                item.shape,
                item.size_x_nm,
                item.size_y_nm,
            ),
        )
    )


def missing_source_land_flashes(
    layers: tuple[GerberLayer, ...],
    requirements: tuple[SourceLandRequirement, ...],
) -> tuple[MissingSourceLandFlashes, ...]:
    """Find source-shaped D03 flashes missing from required source copper layers.

    The accepted Gerber coordinate format has six decimal places. This allows
    half of one six-decimal inch unit (12.7 nm), rounded up, when matching
    coordinates and aperture dimensions to integer-nanometer source geometry.
    """
    unmatched: list[tuple[SourceLandRequirement, list[str]]] = [
        (requirement, []) for requirement in requirements
    ]
    for layer in layers:
        available = _land_flash_index(layer.features)
        for requirement, missing in unmatched:
            if not _requirement_applies_to_layer(requirement, layer.layer):
                continue
            match = _take_matching_flash(available, requirement)
            if match is None:
                missing.append(layer.layer)
    return tuple(
        MissingSourceLandFlashes(requirement, tuple(missing))
        for requirement, missing in unmatched
        if missing
    )


def _requirement_applies_to_layer(requirement: SourceLandRequirement, layer: str) -> bool:
    if requirement.contact_layer == "through":
        return True
    expected = "f.cu" if requirement.contact_layer == "top" else "b.cu"
    return layer.casefold() == expected


def raster_visible_missing_layers(
    missing: MissingSourceLandFlashes,
    assignments: tuple[PadAssignment, ...],
) -> tuple[str, ...]:
    """Keep this finding where raster copper presence would mask a missing land.

    A completely absent contact-layer land remains covered by the existing
    per-layer copper finding. This rule adds a finding where other artwork at
    the contact makes raster connectivity consider the source land present.
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


def _land_aperture_shape(requirement: SourceLandRequirement) -> _ApertureShape:
    shapes: dict[_SourceLandShape, _ApertureShape] = {"circle": "C", "oval": "O", "rect": "R"}
    return shapes[requirement.shape]


def _source_land_shape(value: str | None) -> _SourceLandShape | None:
    if value == "circle":
        return "circle"
    if value == "oval":
        return "oval"
    if value == "rect":
        return "rect"
    return None


def _gerber_aperture_shape(value: str) -> _ApertureShape | None:
    if value == "C":
        return "C"
    if value == "O":
        return "O"
    if value == "R":
        return "R"
    return None


def _land_aperture_sizes(requirement: SourceLandRequirement) -> tuple[int, int]:
    if requirement.shape == "circle":
        return requirement.size_x_nm, 0
    return requirement.size_x_nm, requirement.size_y_nm


def _bucket(value_nm: int) -> int:
    return round(value_nm / _BUCKET_NM)


def _land_flash_index(
    features: tuple[GerberFeature, ...],
) -> dict[_LandFlashKey, list[_LandFlashPoint]]:
    index: dict[_LandFlashKey, list[_LandFlashPoint]] = {}
    for feature in features:
        if feature.kind != "flash" or feature.aperture is None or len(feature.points) != 1:
            continue
        aperture_shape_text, dimensions = feature.aperture
        aperture_shape = _gerber_aperture_shape(aperture_shape_text)
        if aperture_shape is None:
            continue
        if aperture_shape == "C" and len(dimensions) == 1:
            size_x_mm, size_y_mm = dimensions[0], 0.0
        elif aperture_shape in {"O", "R"} and len(dimensions) == 2:
            size_x_mm, size_y_mm = dimensions
        else:
            continue
        x_mm, y_mm = feature.points[0]
        point = (
            round(x_mm * _NM_PER_MM),
            round(y_mm * _NM_PER_MM),
            round(size_x_mm * _NM_PER_MM),
            round(size_y_mm * _NM_PER_MM),
        )
        key = (
            aperture_shape,
            _bucket(point[0]),
            _bucket(point[1]),
            _bucket(point[2]),
            _bucket(point[3]),
        )
        index.setdefault(key, []).append(point)
    for points in index.values():
        points.sort()
    return index


def _take_matching_flash(
    available: dict[_LandFlashKey, list[_LandFlashPoint]],
    requirement: SourceLandRequirement,
) -> _LandFlashPoint | None:
    tolerance = _GERBER_INCH_QUANTIZATION_TOLERANCE_NM
    sizes = _land_aperture_sizes(requirement)
    expected = (requirement.x_nm, requirement.y_nm, *sizes)
    center = tuple(_bucket(value) for value in expected)
    shape = _land_aperture_shape(requirement)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dsx in (-1, 0, 1):
                for dsy in (-1, 0, 1):
                    key = (shape, center[0] + dx, center[1] + dy, center[2] + dsx, center[3] + dsy)
                    candidates = available.get(key, [])
                    for index, candidate in enumerate(candidates):
                        if all(
                            abs(left - right) <= tolerance
                            for left, right in zip(candidate, expected)
                        ):
                            return candidates.pop(index)
    return None
