"""Small deterministic geometry operations shared by schematic checks."""

from __future__ import annotations

import math

from .schematic_geometry_types import POINT_TOLERANCE_MM


def point_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float] | None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return None
    projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    length = math.sqrt(length_squared)
    parameter_tolerance = POINT_TOLERANCE_MM / length
    if projection < -parameter_tolerance or projection > 1.0 + parameter_tolerance:
        return None
    clamped = min(1.0, max(0.0, projection))
    closest = (start[0] + clamped * dx, start[1] + clamped * dy)
    distance = math.hypot(point[0] - closest[0], point[1] - closest[1])
    along = clamped * length
    return distance, along, length


def transform_point(
    point: tuple[float, float],
    origin: tuple[float, float],
    angle: float,
    mirror: str | None,
) -> tuple[float, float]:
    """Match the KiCad 10.0.6 schematic transform, verified with kicad-cli."""
    local_x, local_y = point
    screen_y = -local_y
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    rotated_x = local_x * cosine + screen_y * sine
    rotated_y = -local_x * sine + screen_y * cosine
    if mirror == "x":
        rotated_y = -rotated_y
    elif mirror == "y":
        rotated_x = -rotated_x
    return round(origin[0] + rotated_x, 6), round(origin[1] + rotated_y, 6)


def strictly_inside(value: float, start: float, end: float) -> bool:
    lower, upper = sorted((start, end))
    return value - lower > POINT_TOLERANCE_MM and upper - value > POINT_TOLERANCE_MM


def clip_segment_to_box(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    """Clip one straight segment to an axis-aligned rectangle using Liang-Barsky."""
    x0, y0, x1, y1 = box
    dx, dy = end[0] - start[0], end[1] - start[1]
    lower, upper = 0.0, 1.0
    for denominator, numerator in (
        (-dx, start[0] - x0),
        (dx, x1 - start[0]),
        (-dy, start[1] - y0),
        (dy, y1 - start[1]),
    ):
        if denominator == 0.0:
            if numerator < 0.0:
                return None
            continue
        ratio = numerator / denominator
        if denominator < 0.0:
            if ratio > upper:
                return None
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return None
            upper = min(upper, ratio)
    clipped_start = (start[0] + lower * dx, start[1] + lower * dy)
    clipped_end = (start[0] + upper * dx, start[1] + upper * dy)
    return clipped_start, clipped_end, math.dist(clipped_start, clipped_end)
