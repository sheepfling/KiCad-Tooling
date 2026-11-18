"""Deterministic validation for the supported Gerber region-contour subset."""

from __future__ import annotations

import math

_MAX_REGION_EDGES = 2_048
_PICOMETERS_PER_MM = 1_000_000_000

_Point = tuple[int, int]


def gerber_region_issue(points: list[tuple[float, float]] | None) -> str | None:
    """Return a fail-closed reason when a closed linear region is not simple."""
    if points is None or len(points) < 4 or points[0] != points[-1]:
        return "Gerber region contour must be explicitly closed"
    vertices = points[:-1]
    edge_count = len(vertices)
    if edge_count > _MAX_REGION_EDGES:
        return f"Gerber region contour exceeds {_MAX_REGION_EDGES} supported edges"
    if any(not math.isfinite(value) for point in vertices for value in point):
        return "Gerber region contour has a non-finite coordinate"
    scaled = tuple(
        (round(x * _PICOMETERS_PER_MM), round(y * _PICOMETERS_PER_MM)) for x, y in vertices
    )
    if len(set(scaled)) != edge_count:
        return "Gerber region contour repeats a vertex or has a zero-length edge"
    for index, current in enumerate(scaled):
        previous = scaled[index - 1]
        following = scaled[(index + 1) % edge_count]
        if _orientation(previous, current, following) == 0:
            incoming = previous[0] - current[0], previous[1] - current[1]
            outgoing = following[0] - current[0], following[1] - current[1]
            if incoming[0] * outgoing[0] + incoming[1] * outgoing[1] > 0:
                return "Gerber region contour has overlapping adjacent edges"
    edges = tuple(zip(scaled, (*scaled[1:], scaled[0]), strict=True))
    for left_index, left in enumerate(edges):
        for right_index in range(left_index + 1, edge_count):
            if right_index == left_index + 1 or (left_index == 0 and right_index == edge_count - 1):
                continue
            right = edges[right_index]
            if not _bounds_overlap(left, right):
                continue
            if _segments_intersect(left, right):
                return "Gerber region contour self-intersects or touches itself"
    if _twice_signed_area(scaled) == 0:
        return "Gerber region contour has zero area"
    return None


def _orientation(a: _Point, b: _Point, c: _Point) -> int:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _twice_signed_area(points: tuple[_Point, ...]) -> int:
    return sum(
        point[0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * point[1]
        for index, point in enumerate(points)
    )


def _bounds_overlap(first: tuple[_Point, _Point], second: tuple[_Point, _Point]) -> bool:
    return not (
        max(first[0][0], first[1][0]) < min(second[0][0], second[1][0])
        or max(second[0][0], second[1][0]) < min(first[0][0], first[1][0])
        or max(first[0][1], first[1][1]) < min(second[0][1], second[1][1])
        or max(second[0][1], second[1][1]) < min(first[0][1], first[1][1])
    )


def _segments_intersect(first: tuple[_Point, _Point], second: tuple[_Point, _Point]) -> bool:
    a, b = first
    c, d = second
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if ab_c == 0 and _on_segment(a, c, b):
        return True
    if ab_d == 0 and _on_segment(a, d, b):
        return True
    if cd_a == 0 and _on_segment(c, a, d):
        return True
    if cd_b == 0 and _on_segment(c, b, d):
        return True
    return ab_c * ab_d < 0 and cd_a * cd_b < 0


def _on_segment(a: _Point, point: _Point, b: _Point) -> bool:
    return min(a[0], b[0]) <= point[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= point[1] <= max(
        a[1], b[1]
    )
