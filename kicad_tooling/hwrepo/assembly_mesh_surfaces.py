"""Bounded static triangle surface gap and intersection for placed GLB models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .assembly_clearance_geometry import rotate_point
from .assembly_review_models import AssemblyPlacement
from .three_d_glb import Point3, Triangle3

_MAX_PAIRS = 2_000_000
_CONTACT_TOLERANCE_MM = 1e-6


@dataclass(frozen=True, slots=True)
class MeshSurfaceResult:
    status: Literal["INTERSECTING", "SEPARATED"]
    minimum_gap_mm: float
    board_triangles: int
    enclosure_triangles: int
    tested_pairs: int
    first_intersection: tuple[int, int] | None


def _sub(a: Point3, b: Point3) -> Point3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _add(a: Point3, b: Point3) -> Point3:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _scale(a: Point3, factor: float) -> Point3:
    return a[0] * factor, a[1] * factor, a[2] * factor


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _edges(triangle: Triangle3) -> tuple[Point3, Point3, Point3]:
    a, b, c = triangle
    return _sub(b, a), _sub(c, b), _sub(a, c)


def _normal(triangle: Triangle3) -> Point3:
    a, b, c = triangle
    return _cross(_sub(b, a), _sub(c, a))


def _bounds(triangle: Triangle3) -> tuple[Point3, Point3]:
    return (
        tuple(min(point[axis] for point in triangle) for axis in range(3)),
        tuple(max(point[axis] for point in triangle) for axis in range(3)),
    )  # type: ignore[return-value]


def _bounds_gap_sq(a: tuple[Point3, Point3], b: tuple[Point3, Point3]) -> float:
    return sum(max(b[0][axis] - a[1][axis], a[0][axis] - b[1][axis], 0.0) ** 2 for axis in range(3))


def _scaled_triangle(triangle: Triangle3, factor: float) -> Triangle3:
    return _scale(triangle[0], factor), _scale(triangle[1], factor), _scale(triangle[2], factor)


def _placed_triangle(
    triangle: Triangle3,
    factor: float,
    placement: AssemblyPlacement,
) -> Triangle3:
    def place(point: Point3) -> Point3:
        return _add(
            rotate_point(_scale(point, factor), placement.rotation_xyzw),
            placement.translation_mm,
        )

    return place(triangle[0]), place(triangle[1]), place(triangle[2])


def _intersect(a: Triangle3, b: Triangle3) -> bool:
    a_edges, b_edges = _edges(a), _edges(b)
    a_normal, b_normal = _normal(a), _normal(b)
    axes = (
        a_normal,
        b_normal,
        *(_cross(x, y) for x in a_edges for y in b_edges),
        *(_cross(a_normal, edge) for edge in (*a_edges, *b_edges)),
    )
    for axis in axes:
        size = math.sqrt(_dot(axis, axis))
        if size < 1e-12:
            continue
        projected_a = tuple(_dot(point, axis) / size for point in a)
        projected_b = tuple(_dot(point, axis) / size for point in b)
        if (
            max(projected_a) < min(projected_b) - _CONTACT_TOLERANCE_MM
            or max(projected_b) < min(projected_a) - _CONTACT_TOLERANCE_MM
        ):
            return False
    return True


def _point_segment_sq(point: Point3, start: Point3, end: Point3) -> float:
    direction = _sub(end, start)
    t = max(0.0, min(1.0, _dot(_sub(point, start), direction) / _dot(direction, direction)))
    difference = _sub(point, _add(start, _scale(direction, t)))
    return _dot(difference, difference)


def _point_triangle_sq(point: Point3, triangle: Triangle3) -> float:
    a, b, c = triangle
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(point, a)
    d00, d01, d11 = _dot(ab, ab), _dot(ab, ac), _dot(ac, ac)
    d20, d21 = _dot(ap, ab), _dot(ap, ac)
    denominator = d00 * d11 - d01 * d01
    u = (d11 * d20 - d01 * d21) / denominator
    v = (d00 * d21 - d01 * d20) / denominator
    if u >= 0 and v >= 0 and u + v <= 1:
        normal = _normal(triangle)
        return _dot(ap, normal) ** 2 / _dot(normal, normal)
    return min(
        _point_segment_sq(point, a, b),
        _point_segment_sq(point, b, c),
        _point_segment_sq(point, c, a),
    )


def _segment_segment_sq(a: Point3, b: Point3, c: Point3, d: Point3) -> float:
    minimum = min(
        _point_segment_sq(a, c, d),
        _point_segment_sq(b, c, d),
        _point_segment_sq(c, a, b),
        _point_segment_sq(d, a, b),
    )
    u, v, w = _sub(b, a), _sub(d, c), _sub(a, c)
    uu, uv, vv = _dot(u, u), _dot(u, v), _dot(v, v)
    denominator = uu * vv - uv * uv
    if denominator > 1e-20:
        s = (uv * _dot(v, w) - vv * _dot(u, w)) / denominator
        t = (uu * _dot(v, w) - uv * _dot(u, w)) / denominator
        if 0 <= s <= 1 and 0 <= t <= 1:
            delta = _sub(_add(a, _scale(u, s)), _add(c, _scale(v, t)))
            minimum = min(minimum, _dot(delta, delta))
    return minimum


def _distance_sq(a: Triangle3, b: Triangle3) -> float:
    result = min(
        *(_point_triangle_sq(point, b) for point in a),
        *(_point_triangle_sq(point, a) for point in b),
    )
    for first in ((a[0], a[1]), (a[1], a[2]), (a[2], a[0])):
        for second in ((b[0], b[1]), (b[1], b[2]), (b[2], b[0])):
            result = min(result, _segment_segment_sq(*first, *second))
    return result


def compare_mesh_surfaces(
    board: tuple[Triangle3, ...],
    enclosure: tuple[Triangle3, ...],
    *,
    board_unit: Literal["mm", "m"],
    enclosure_unit: Literal["mm", "m"],
    placement: AssemblyPlacement,
) -> MeshSurfaceResult:
    """Compare complete supported surfaces in the board frame; fail closed on scale limits."""
    if not board or not enclosure or len(board) * len(enclosure) > _MAX_PAIRS:
        raise ValueError("Mesh surface comparison exceeds its supported triangle-pair limit")
    board_scale = 1000 if board_unit == "m" else 1
    enclosure_scale = 1000 if enclosure_unit == "m" else 1
    placed_board = tuple(_scaled_triangle(triangle, board_scale) for triangle in board)
    placed_enclosure = tuple(
        _placed_triangle(triangle, enclosure_scale, placement) for triangle in enclosure
    )
    for triangle in (*placed_board, *placed_enclosure):
        if not all(math.isfinite(value) for point in triangle for value in point):
            raise ValueError("Placed mesh coordinates are not finite")
        if _dot(_normal(triangle), _normal(triangle)) < 1e-24:
            raise ValueError("Degenerate mesh triangle leaves surface comparison unassessed")
    enclosure_bounds = tuple(_bounds(triangle) for triangle in placed_enclosure)
    minimum_sq = math.inf
    tested = 0
    for board_index, board_triangle in enumerate(placed_board):
        board_bounds = _bounds(board_triangle)
        for enclosure_index, enclosure_triangle in enumerate(placed_enclosure):
            lower_bound = _bounds_gap_sq(board_bounds, enclosure_bounds[enclosure_index])
            if lower_bound > max(minimum_sq, _CONTACT_TOLERANCE_MM**2):
                continue
            tested += 1
            if lower_bound <= _CONTACT_TOLERANCE_MM**2 and _intersect(
                board_triangle, enclosure_triangle
            ):
                return MeshSurfaceResult(
                    status="INTERSECTING",
                    minimum_gap_mm=0.0,
                    board_triangles=len(board),
                    enclosure_triangles=len(enclosure),
                    tested_pairs=tested,
                    first_intersection=(board_index, enclosure_index),
                )
            minimum_sq = min(minimum_sq, _distance_sq(board_triangle, enclosure_triangle))
    return MeshSurfaceResult(
        status="SEPARATED",
        minimum_gap_mm=math.sqrt(minimum_sq),
        board_triangles=len(board),
        enclosure_triangles=len(enclosure),
        tested_pairs=tested,
        first_intersection=None,
    )
