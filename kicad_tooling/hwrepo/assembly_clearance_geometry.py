"""Measure static board triangle vertices against an authored free-space box."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .assembly_clearance_models import AssemblyFreeSpaceBox
from .assembly_review_models import AssemblyPlacement
from .three_d_glb import Point3

BoxStatus = Literal["CLEAR_WITHIN_BOX", "LOW_CLEARANCE", "BOX_INTERFERENCE"]


@dataclass(frozen=True, slots=True)
class BoxMarginResult:
    status: BoxStatus
    face_margins_mm: dict[str, float]
    minimum_margin_mm: float
    referenced_vertices: int


def rotate_point(point: Point3, quaternion: tuple[float, float, float, float]) -> Point3:
    x, y, z = point
    qx, qy, qz, qw = quaternion
    tx = 2 * (qy * z - qz * y)
    ty = 2 * (qz * x - qx * z)
    tz = 2 * (qx * y - qy * x)
    return (
        x + qw * tx + qy * tz - qz * ty,
        y + qw * ty + qz * tx - qx * tz,
        z + qw * tz + qx * ty - qy * tx,
    )


def measure_free_space_box(
    vertices: tuple[Point3, ...],
    *,
    board_unit: Literal["mm", "m"],
    enclosure_unit: Literal["mm", "m"],
    placement: AssemblyPlacement,
    free_space: AssemblyFreeSpaceBox,
    required_margin_mm: float,
) -> BoxMarginResult:
    """Return exact face margins for the supported static triangle vertices."""
    if not vertices or required_margin_mm < 0 or not math.isfinite(required_margin_mm):
        raise ValueError("Clearance review needs vertices and a finite nonnegative margin")
    board_scale = 1000 if board_unit == "m" else 1
    enclosure_scale = 1000 if enclosure_unit == "m" else 1
    lower = tuple(value * enclosure_scale for value in free_space.lower)
    upper = tuple(value * enclosure_scale for value in free_space.upper)
    if not all(math.isfinite(value) for value in (*lower, *upper)):
        raise ValueError("Free-space bounds exceed finite millimetres")
    qx, qy, qz, qw = placement.rotation_xyzw
    inverse = (-qx, -qy, -qz, qw)
    translation = placement.translation_mm
    margins = {
        "x_min": math.inf,
        "x_max": math.inf,
        "y_min": math.inf,
        "y_max": math.inf,
        "z_min": math.inf,
        "z_max": math.inf,
    }
    for vertex in vertices:
        board_mm: Point3 = tuple(
            value * board_scale - translation[index] for index, value in enumerate(vertex)
        )  # type: ignore[assignment]
        local = rotate_point(board_mm, inverse)
        if not all(math.isfinite(value) for value in local):
            raise ValueError("Transformed board geometry exceeds finite millimetres")
        for axis, coordinate in enumerate(local):
            letter = "xyz"[axis]
            margins[f"{letter}_min"] = min(margins[f"{letter}_min"], coordinate - lower[axis])
            margins[f"{letter}_max"] = min(margins[f"{letter}_max"], upper[axis] - coordinate)
    minimum = min(margins.values())
    status: BoxStatus = (
        "BOX_INTERFERENCE"
        if minimum < -1e-6
        else "LOW_CLEARANCE"
        if minimum < max(required_margin_mm, 1e-6)
        else "CLEAR_WITHIN_BOX"
    )
    return BoxMarginResult(
        status=status,
        face_margins_mm=margins,
        minimum_margin_mm=minimum,
        referenced_vertices=len(vertices),
    )
