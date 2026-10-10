"""Focused switching-loop analysis: pcb switching loop geometry."""

from __future__ import annotations

from .pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbZoneFilledIslandObservation,
)
from .pcb_switching_loop_models import (
    PcbSwitchingLoopRequirement,
)


def _orientation(first: tuple[int, int], second: tuple[int, int], third: tuple[int, int]) -> int:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (
        third[0] - first[0]
    )


def _on_segment(first: tuple[int, int], second: tuple[int, int], point: tuple[int, int]) -> bool:
    return min(first[0], second[0]) <= point[0] <= max(first[0], second[0]) and min(
        first[1], second[1]
    ) <= point[1] <= max(first[1], second[1])


def _segments_intersect(
    a: tuple[int, int], b: tuple[int, int], c: tuple[int, int], d: tuple[int, int]
) -> bool:
    first = _orientation(a, b, c)
    second = _orientation(a, b, d)
    third = _orientation(c, d, a)
    fourth = _orientation(c, d, b)
    if first == 0 and _on_segment(a, b, c):
        return True
    if second == 0 and _on_segment(a, b, d):
        return True
    if third == 0 and _on_segment(c, d, a):
        return True
    if fourth == 0 and _on_segment(c, d, b):
        return True
    return (first < 0) != (second < 0) and (third < 0) != (fourth < 0)


def _self_intersects(points: tuple[tuple[int, int], ...]) -> bool:
    count = len(points)
    for first_index in range(count):
        first_next = (first_index + 1) % count
        for second_index in range(first_index + 1, count):
            second_next = (second_index + 1) % count
            if (
                first_index == second_index
                or first_next == second_index
                or second_next == first_index
            ):
                continue
            if _segments_intersect(
                points[first_index],
                points[first_next],
                points[second_index],
                points[second_next],
            ):
                return True
    return False


def loop_area_twice_nm2(
    requirement: PcbSwitchingLoopRequirement,
    pads: dict[str, PcbPadConnectivityObservation],
) -> tuple[int | None, list[str]]:
    issues: list[str] = []
    points: list[tuple[int, int]] = []
    for expected in requirement.loop_pads:
        observed = pads.get(expected.pad.casefold())
        if observed is None:
            issues.append(f"Mapped loop pad {expected.pad} is absent from the native PCB inventory")
            continue
        if observed.footprint != expected.footprint:
            issues.append(
                f"Mapped loop pad {expected.pad} uses footprint {observed.footprint!r}; "
                f"expected {expected.footprint!r}"
            )
        if observed.net != expected.net:
            issues.append(
                f"Mapped loop pad {expected.pad} uses net {observed.net!r}; expected {expected.net!r}"
            )
        if observed.dnp:
            issues.append(f"Mapped loop pad {expected.pad} is marked do-not-populate")
        if len(observed.positions_nm) != 1:
            issues.append(
                f"Mapped loop pad {expected.pad} has {len(observed.positions_nm)} native centers; "
                "exactly one is required"
            )
        else:
            points.append(observed.positions_nm[0])
    if issues:
        return None, issues
    polygon = tuple(points)
    if len(set(polygon)) != len(polygon):
        return None, ["Mapped loop pad centers are not geometrically distinct"]
    if _self_intersects(polygon):
        return None, ["Authored switching-loop pad order forms a self-intersecting polygon"]
    area_twice = abs(
        sum(
            point[0] * polygon[(index + 1) % len(polygon)][1]
            - polygon[(index + 1) % len(polygon)][0] * point[1]
            for index, point in enumerate(polygon)
        )
    )
    if area_twice == 0:
        return None, ["Mapped switching-loop pad centers form a zero-area polygon"]
    return area_twice, issues


def _ring_area_twice_nm2(ring: tuple[tuple[int, int], ...]) -> int:
    return sum(
        point[0] * ring[(index + 1) % len(ring)][1] - ring[(index + 1) % len(ring)][0] * point[1]
        for index, point in enumerate(ring)
    )


def filled_island_area_twice_nm2(
    island: PcbZoneFilledIslandObservation,
) -> int | None:
    area = abs(_ring_area_twice_nm2(island.outline_nm)) - sum(
        abs(_ring_area_twice_nm2(hole)) for hole in island.holes_nm
    )
    return area if area > 0 else None
