"""Wire, label, crossing, and T-junction geometry heuristics."""

from __future__ import annotations

import math
from itertools import pairwise

from .model_inventory import _atoms, _Span  # pyright: ignore[reportPrivateUsage]
from .schematic_geometry_primitives import point_to_segment, strictly_inside
from .schematic_geometry_source import schematic_at, schematic_nodes, schematic_number
from .schematic_geometry_types import (
    DISTANCE_COMPARISON_EPSILON_MM,
    LABEL_KINDS,
    MAX_LABEL_ENDPOINT_GAP_MM,
    POINT_TOLERANCE_MM,
    LabelAnchor,
    LabelNearWireEndpoint,
    LabelWireEndpointCandidate,
    SchematicPin,
    UnmarkedTJunction,
    UnmarkedWireCrossing,
    WireEnd,
    WireSegment,
)


def wire_geometry(
    source: str, root: _Span
) -> tuple[tuple[WireEnd, ...], tuple[WireSegment, ...], tuple[str, ...]]:
    ends: list[WireEnd] = []
    segments: list[WireSegment] = []
    unsupported: list[str] = []
    for wire in schematic_nodes(source, root, "wire"):
        uuids = schematic_nodes(source, wire, "uuid")
        points_sections = schematic_nodes(source, wire, "pts")
        if len(uuids) != 1 or len(points_sections) != 1:
            unsupported.append("wire without a unique UUID or point list")
            continue
        uuid_atoms = _atoms(source, uuids[0])
        if len(uuid_atoms) != 2:
            unsupported.append("wire with malformed UUID")
            continue
        coords: list[tuple[float, float]] = []
        for point in schematic_nodes(source, points_sections[0], "xy"):
            atoms = _atoms(source, point)
            if len(atoms) != 3:
                unsupported.append(f"wire {uuid_atoms[1]} has malformed coordinate")
                coords = []
                break
            coords.append(
                (
                    schematic_number(atoms[1], "wire x coordinate"),
                    schematic_number(atoms[2], "wire y coordinate"),
                )
            )
        if len(coords) < 2:
            unsupported.append(f"wire {uuid_atoms[1]} has fewer than two points")
            continue
        ends.extend(
            (
                WireEnd(uuid=uuid_atoms[1], point=coords[0]),
                WireEnd(uuid=uuid_atoms[1], point=coords[-1]),
            )
        )
        segments.extend(
            WireSegment(uuid=uuid_atoms[1], start=start, end=end) for start, end in pairwise(coords)
        )
    return tuple(ends), tuple(segments), tuple(unsupported)


def no_connect_points(source: str, root: _Span) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for node in schematic_nodes(source, root, "no_connect"):
        x, y, _ = schematic_at(source, node, angle_required=False)
        points.append((x, y))
    return tuple(points)


def junction_points(
    source: str, root: _Span
) -> tuple[tuple[tuple[float, float], ...], tuple[str, ...]]:
    points: list[tuple[float, float]] = []
    unsupported: list[str] = []
    for node in schematic_nodes(source, root, "junction"):
        uuids = schematic_nodes(source, node, "uuid")
        try:
            x, y, _angle = schematic_at(source, node, angle_required=False)
        except ValueError as exc:
            identity = _atoms(source, uuids[0])[-1] if len(uuids) == 1 else "unknown"
            unsupported.append(f"junction {identity} has invalid location: {exc}")
            continue
        points.append((x, y))
    return tuple(points), tuple(unsupported)


def unmarked_orthogonal_crossings(
    segments: tuple[WireSegment, ...], junctions: tuple[tuple[float, float], ...]
) -> tuple[UnmarkedWireCrossing, ...]:
    wires_by_point: dict[tuple[float, float], set[str]] = {}
    for index, first in enumerate(segments):
        first_horizontal = abs(first.start[1] - first.end[1]) <= POINT_TOLERANCE_MM
        first_vertical = abs(first.start[0] - first.end[0]) <= POINT_TOLERANCE_MM
        if first_horizontal == first_vertical:
            continue
        for second in segments[index + 1 :]:
            if first.uuid == second.uuid:
                continue
            second_horizontal = abs(second.start[1] - second.end[1]) <= POINT_TOLERANCE_MM
            second_vertical = abs(second.start[0] - second.end[0]) <= POINT_TOLERANCE_MM
            if first_horizontal and second_vertical:
                horizontal, vertical = first, second
            elif first_vertical and second_horizontal:
                horizontal, vertical = second, first
            else:
                continue
            x = (vertical.start[0] + vertical.end[0]) / 2
            y = (horizontal.start[1] + horizontal.end[1]) / 2
            if (
                abs(vertical.start[0] - vertical.end[0]) > POINT_TOLERANCE_MM
                or abs(horizontal.start[1] - horizontal.end[1]) > POINT_TOLERANCE_MM
                or not strictly_inside(x, horizontal.start[0], horizontal.end[0])
                or not strictly_inside(y, vertical.start[1], vertical.end[1])
                or any(math.dist((x, y), marker) <= POINT_TOLERANCE_MM for marker in junctions)
            ):
                continue
            point = (round(x, 6), round(y, 6))
            wires_by_point.setdefault(point, set()).update((first.uuid, second.uuid))
    return tuple(
        UnmarkedWireCrossing(wire_uuids=tuple(sorted(uuids)), crossing_mm=point)
        for point, uuids in sorted(wires_by_point.items())
    )


def unmarked_t_junctions(
    wire_ends: tuple[WireEnd, ...],
    segments: tuple[WireSegment, ...],
    junctions: tuple[tuple[float, float], ...],
) -> tuple[UnmarkedTJunction, ...]:
    findings: dict[tuple[str, str, tuple[float, float]], UnmarkedTJunction] = {}
    for endpoint in wire_ends:
        for segment in segments:
            if endpoint.uuid == segment.uuid:
                continue
            measurement = point_to_segment(endpoint.point, segment.start, segment.end)
            if measurement is None:
                continue
            distance, along, length = measurement
            if (
                distance > POINT_TOLERANCE_MM
                or along <= POINT_TOLERANCE_MM
                or length - along <= POINT_TOLERANCE_MM
                or any(
                    math.dist(endpoint.point, marker) <= POINT_TOLERANCE_MM for marker in junctions
                )
            ):
                continue
            point = (round(endpoint.point[0], 6), round(endpoint.point[1], 6))
            key = (endpoint.uuid, segment.uuid, point)
            findings[key] = UnmarkedTJunction(
                endpoint_wire_uuid=endpoint.uuid,
                interior_wire_uuid=segment.uuid,
                junction_mm=point,
            )
    return tuple(
        findings[key] for key in sorted(findings, key=lambda item: (item[2], item[0], item[1]))
    )


def label_anchors(source: str, root: _Span) -> tuple[tuple[LabelAnchor, ...], tuple[str, ...]]:
    labels: list[LabelAnchor] = []
    unsupported: list[str] = []
    for kind in LABEL_KINDS:
        for node in schematic_nodes(source, root, kind):
            atoms = _atoms(source, node)
            uuids = schematic_nodes(source, node, "uuid")
            if len(atoms) < 2 or len(uuids) != 1:
                unsupported.append(f"{kind} without a name or unique UUID")
                continue
            uuid_atoms = _atoms(source, uuids[0])
            if len(uuid_atoms) != 2 or not uuid_atoms[1]:
                unsupported.append(f"{kind} with malformed UUID")
                continue
            try:
                x, y, _angle = schematic_at(source, node, angle_required=True)
            except ValueError as exc:
                unsupported.append(f"{kind} {uuid_atoms[1]} has invalid anchor: {exc}")
                continue
            labels.append(
                LabelAnchor(
                    kind=kind,
                    text=atoms[1],
                    uuid=uuid_atoms[1],
                    point=(x, y),
                )
            )
    return tuple(labels), tuple(unsupported)


def labels_near_wire_endpoints(
    labels: tuple[LabelAnchor, ...],
    pins: list[SchematicPin],
    wire_ends: tuple[WireEnd, ...],
    wire_segments: tuple[WireSegment, ...],
) -> tuple[LabelNearWireEndpoint, ...]:
    findings: list[LabelNearWireEndpoint] = []
    for label in labels:
        if any(
            (measurement := point_to_segment(label.point, segment.start, segment.end)) is not None
            and measurement[0] <= POINT_TOLERANCE_MM
            for segment in wire_segments
        ) or any(math.dist(label.point, pin.tip) <= POINT_TOLERANCE_MM for pin in pins):
            continue

        candidates = tuple(
            sorted(
                {
                    (wire_end.uuid, wire_end.point): LabelWireEndpointCandidate(
                        wire_uuid=wire_end.uuid,
                        wire_endpoint_mm=wire_end.point,
                        distance_mm=round(distance, 6),
                    )
                    for wire_end in wire_ends
                    if POINT_TOLERANCE_MM
                    < (distance := math.dist(label.point, wire_end.point))
                    <= MAX_LABEL_ENDPOINT_GAP_MM + DISTANCE_COMPARISON_EPSILON_MM
                }.values(),
                key=lambda item: (
                    item.distance_mm,
                    item.wire_uuid,
                    item.wire_endpoint_mm,
                ),
            )
        )
        if candidates:
            findings.append(
                LabelNearWireEndpoint(
                    label_kind=label.kind,
                    text=label.text,
                    label_uuid=label.uuid,
                    anchor_mm=label.point,
                    candidates=candidates,
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.label_kind, item.label_uuid)))
