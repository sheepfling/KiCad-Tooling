"""Deterministic review of authored switching-loop and return-plane mappings."""

from __future__ import annotations

from collections import deque
from math import isqrt
from typing import Literal

from .models import (
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbSwitchingLoopCoverageEntry,
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopRequirement,
    PcbSwitchingLoopRouteEdgeCoverage,
    PcbTrackObservation,
    PcbZoneFilledIslandObservation,
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


def _loop_area_twice_nm2(
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


def _return_plane(
    requirement: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> tuple[
    Literal["CONNECTED", "SPLIT", "UNOBSERVED", "UNSUPPORTED", "AMBIGUOUS"],
    str | None,
    int | None,
    list[str],
]:
    issues: list[str] = []
    if requirement.return_plane_layer.casefold() not in {
        layer.casefold() for layer in snapshot.copper_layers
    }:
        return (
            "UNSUPPORTED",
            None,
            None,
            [
                f"Return-plane layer {requirement.return_plane_layer!r} is absent from the native copper stack inventory"
            ],
        )

    zones = {(item.uuid.casefold(), item.layer.casefold()): item for item in snapshot.zones}
    common: set[tuple[str, int]] | None = None
    any_anchor = False
    for expected in requirement.return_plane_pads:
        observed = pads.get(expected.pad.casefold())
        if observed is None:
            issues.append(
                f"Mapped return-plane pad {expected.pad} is absent from the native PCB inventory"
            )
            anchors: set[tuple[str, int]] = set()
        else:
            if observed.footprint != expected.footprint:
                issues.append(
                    f"Mapped return-plane pad {expected.pad} uses footprint "
                    f"{observed.footprint!r}; expected {expected.footprint!r}"
                )
            if observed.net is None or observed.net.casefold() != requirement.return_net.casefold():
                issues.append(
                    f"Mapped return-plane pad {expected.pad} uses net {observed.net!r}; "
                    f"expected {requirement.return_net!r}"
                )
            if observed.dnp:
                issues.append(f"Mapped return-plane pad {expected.pad} is marked do-not-populate")
            anchors = set()
            for island in observed.connected_islands:
                if island.layer.casefold() != requirement.return_plane_layer.casefold():
                    continue
                zone = zones.get((island.uuid.casefold(), island.layer.casefold()))
                if (
                    zone is not None
                    and zone.net is not None
                    and (zone.net.casefold() == requirement.return_net.casefold())
                ):
                    anchors.add((island.uuid.casefold(), island.island_index))
            any_anchor = any_anchor or bool(anchors)
        common = anchors if common is None else common & anchors

    if issues:
        return "UNOBSERVED", None, None, issues
    shared_islands = common or set()
    if len(shared_islands) == 1:
        zone_uuid, island_index = next(iter(shared_islands))
        return "CONNECTED", zone_uuid, island_index, issues
    if len(shared_islands) > 1:
        return (
            "AMBIGUOUS",
            None,
            None,
            ["Mapped return pads share more than one same-net filled zone island identity"],
        )
    if any_anchor:
        return (
            "SPLIT",
            None,
            None,
            ["Mapped return pads do not share one filled island in the declared return-plane zone"],
        )
    return (
        "UNOBSERVED",
        None,
        None,
        [
            "No filled zone island on the declared return-plane layer is observed at every mapped return pad"
        ],
    )


class _RouteUnion:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, node: str) -> None:
        self.parent.setdefault(node, node)

    def find(self, node: str) -> str:
        self.add(node)
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def join(self, first: str, second: str) -> None:
        left = self.find(first)
        right = self.find(second)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def _endpoint_node(track_uuid: str, side: str) -> str:
    return f"track:{track_uuid.casefold()}:{side}"


def _endpoint_records(
    track: PcbTrackObservation,
) -> tuple[tuple[str, tuple[int, int], tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...]:
    return (
        (
            "start",
            track.start_nm,
            track.start_pads,
            track.start_vias,
            track.start_tracks,
        ),
        ("end", track.end_nm, track.end_pads, track.end_vias, track.end_tracks),
    )


def _rounded_segment_length_nm(first: tuple[int, int], second: tuple[int, int]) -> int:
    squared = (second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2
    floor = isqrt(squared)
    return floor + (4 * squared >= (2 * floor + 1) ** 2)


def _ring_area_twice_nm2(ring: tuple[tuple[int, int], ...]) -> int:
    return sum(
        point[0] * ring[(index + 1) % len(ring)][1] - ring[(index + 1) % len(ring)][0] * point[1]
        for index, point in enumerate(ring)
    )


def _filled_island_area_twice_nm2(
    island: PcbZoneFilledIslandObservation,
) -> int | None:
    area = abs(_ring_area_twice_nm2(island.outline_nm)) - sum(
        abs(_ring_area_twice_nm2(hole)) for hole in island.holes_nm
    )
    return area if area > 0 else None


def _incomplete_edge(
    index: int, edge: PcbSwitchingLoopEdge, issue: str, tracks: tuple[str, ...] = ()
) -> PcbSwitchingLoopRouteEdgeCoverage:
    return PcbSwitchingLoopRouteEdgeCoverage(
        edge_index=index,
        from_pad=edge.from_pad,
        to_pad=edge.to_pad,
        kind=edge.kind,
        status="INCOMPLETE",
        track_uuids=tracks,
        issue=issue,
    )


def _mapped_endpoint_issue(
    edge: PcbSwitchingLoopEdge,
    specification: PcbSwitchingLoopRequirement,
    pads: dict[str, PcbPadConnectivityObservation],
) -> str | None:
    expected = {item.pad.casefold(): item for item in specification.loop_pads}
    for reference in (edge.from_pad, edge.to_pad):
        item = pads.get(reference.casefold())
        mapped = expected[reference.casefold()]
        if item is None:
            return f"Mapped edge pad {reference} is absent from the native PCB inventory"
        if item.footprint != mapped.footprint:
            return (
                f"Mapped edge pad {reference} uses footprint {item.footprint!r}; "
                f"expected {mapped.footprint!r}"
            )
        if item.net != mapped.net:
            return f"Mapped edge pad {reference} uses net {item.net!r}; expected {mapped.net!r}"
        if item.dnp:
            return f"Mapped edge pad {reference} is marked do-not-populate"
        if len(item.positions_nm) != 1:
            return f"Mapped edge pad {reference} needs exactly one native center"
    return None


def _resolve_trace_edge(
    index: int,
    edge: PcbSwitchingLoopEdge,
    specification: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> PcbSwitchingLoopRouteEdgeCoverage:
    endpoint_issue = _mapped_endpoint_issue(edge, specification, pads)
    if endpoint_issue is not None:
        return _incomplete_edge(index, edge, endpoint_issue)
    if snapshot.schema_version not in {"8", "9", "10"}:
        return _incomplete_edge(
            index, edge, "Native track endpoint-contact evidence requires PCB snapshot schema 8+"
        )
    allowed_layers = {layer.casefold() for layer in edge.layers}
    copper_layers = {layer.casefold() for layer in snapshot.copper_layers}
    if not allowed_layers <= copper_layers:
        return _incomplete_edge(
            index,
            edge,
            "Trace edge declares a copper layer absent from the native board stack",
        )

    tracks_by_id = {item.uuid.casefold(): item for item in snapshot.tracks}
    candidates = {
        item.uuid.casefold(): item
        for item in snapshot.tracks
        if item.net is not None
        and item.net.casefold() == (edge.net or "").casefold()
        and item.layer.casefold() in allowed_layers
    }
    if not candidates:
        return _incomplete_edge(
            index, edge, "No native track is observed in the declared net/layer scope"
        )

    union = _RouteUnion()
    pads_by_node: dict[str, set[str]] = {}
    for track in candidates.values():
        for side, point, endpoint_pads, endpoint_vias, endpoint_tracks in _endpoint_records(track):
            node = _endpoint_node(track.uuid, side)
            union.add(node)
            for reference in endpoint_pads:
                pad_node = f"pad:{reference.casefold()}"
                union.join(node, pad_node)
                pads_by_node.setdefault(pad_node, set()).add(reference)
            for via_id in endpoint_vias:
                via_node = f"via:{via_id}"
                union.join(node, via_node)
            for neighbor_id in endpoint_tracks:
                neighbor = tracks_by_id.get(neighbor_id.casefold())
                if neighbor is None:
                    return _incomplete_edge(
                        index, edge, "Native endpoint adjacency refers to an absent track"
                    )
                if (
                    neighbor.net is None
                    or neighbor.net.casefold() != (edge.net or "").casefold()
                    or neighbor.layer.casefold() not in allowed_layers
                ):
                    return _incomplete_edge(
                        index,
                        edge,
                        "A native track connected at this endpoint lies outside the declared net/layer scope",
                    )
                matches = tuple(
                    (neighbor_side, neighbor_point, _endpoint_node(neighbor.uuid, neighbor_side))
                    for neighbor_side, neighbor_point, _pads, _vias, neighbor_tracks in _endpoint_records(
                        neighbor
                    )
                    if neighbor_point == point
                    and track.uuid.casefold() in {value.casefold() for value in neighbor_tracks}
                )
                if len(matches) != 1:
                    return _incomplete_edge(
                        index,
                        edge,
                        "Native connected-track evidence does not resolve to one matching endpoint vertex",
                    )
                union.join(node, matches[0][2])

    vias_by_id = {item.id: item for item in snapshot.vias}
    for track in candidates.values():
        for _side, _point, _endpoint_pads, endpoint_vias, _endpoint_tracks in _endpoint_records(
            track
        ):
            for via_id in endpoint_vias:
                via = vias_by_id.get(via_id)
                if via is None:
                    return _incomplete_edge(index, edge, "Native endpoint refers to an absent via")
                if via.net is None or via.net.casefold() != (edge.net or "").casefold():
                    return _incomplete_edge(index, edge, "Native endpoint via has a different net")
                if (
                    via.start_layer.casefold() not in allowed_layers
                    or via.end_layer.casefold() not in allowed_layers
                ):
                    return _incomplete_edge(
                        index,
                        edge,
                        "Native via layer transition exceeds the declared trace-layer scope",
                    )

    graph: dict[str, list[tuple[str, str]]] = {}
    track_roots: dict[str, tuple[str, str]] = {}
    for track in candidates.values():
        start_root = union.find(_endpoint_node(track.uuid, "start"))
        end_root = union.find(_endpoint_node(track.uuid, "end"))
        track_roots[track.uuid.casefold()] = (start_root, end_root)
        graph.setdefault(start_root, []).append((end_root, track.uuid.casefold()))
        graph.setdefault(end_root, []).append((start_root, track.uuid.casefold()))

    source_node = f"pad:{edge.from_pad.casefold()}"
    target_node = f"pad:{edge.to_pad.casefold()}"
    if source_node not in union.parent or target_node not in union.parent:
        return _incomplete_edge(
            index, edge, "No native track endpoint contacts one or both mapped pads"
        )
    source_root = union.find(source_node)
    target_root = union.find(target_node)
    if source_root == target_root:
        return _incomplete_edge(
            index,
            edge,
            "Mapped pads collapse to one native endpoint vertex without a measured track path",
        )
    parents: dict[str, str | None] = {source_root: None}
    parent_tracks: dict[str, str] = {}
    pending = deque([source_root])
    has_branch = False
    has_cycle = False
    while pending:
        node = pending.popleft()
        neighbors = sorted(graph.get(node, ()), key=lambda row: (row[1], row[0]))
        has_branch = has_branch or len(neighbors) > 2
        for neighbor, track_id in neighbors:
            if neighbor not in parents:
                parents[neighbor] = node
                parent_tracks[neighbor] = track_id
                pending.append(neighbor)
            elif parent_tracks.get(node) != track_id and parent_tracks.get(neighbor) != track_id:
                has_cycle = True
    if target_root not in parents:
        return _incomplete_edge(index, edge, "No native track chain connects the exact mapped pads")
    if has_branch:
        return _incomplete_edge(
            index,
            edge,
            "The mapped net/layer component has a connected branch; route selection is ambiguous",
        )
    if has_cycle:
        return _incomplete_edge(
            index, edge, "More than one native track chain connects the mapped pads"
        )
    node_path_reversed = [target_root]
    track_path_reversed: list[str] = []
    current = target_root
    while current != source_root:
        parent = parents[current]
        if parent is None:
            return _incomplete_edge(index, edge, "Native route predecessor chain is incomplete")
        node_path_reversed.append(parent)
        track_path_reversed.append(parent_tracks[current])
        current = parent
    node_path = tuple(reversed(node_path_reversed))
    track_path = tuple(reversed(track_path_reversed))
    for node in node_path:
        connected_pads = {
            reference.casefold()
            for pad_node, references in pads_by_node.items()
            if union.find(pad_node) == node
            for reference in references
        }
        if connected_pads - {edge.from_pad.casefold(), edge.to_pad.casefold()}:
            return _incomplete_edge(
                index,
                edge,
                "The mapped track chain contacts another pad in the same copper path",
                track_path,
            )

    path_tracks = tuple(tracks_by_id[track_id] for track_id in track_path)
    if any(track.geometry_kind != "segment" for track in path_tracks):
        return _incomplete_edge(
            index,
            edge,
            "The resolved path contains unsupported arc geometry",
            track_path,
        )
    vertices: list[tuple[int, int]] = []
    length_nm = 0
    for track_id, from_node, to_node in zip(track_path, node_path[:-1], node_path[1:], strict=True):
        track = tracks_by_id[track_id]
        start_root, end_root = track_roots[track_id]
        if from_node == start_root and to_node == end_root:
            ordered = (track.start_nm, track.end_nm)
        elif from_node == end_root and to_node == start_root:
            ordered = (track.end_nm, track.start_nm)
        else:
            return _incomplete_edge(
                index, edge, "Resolved route order differs from native track endpoints"
            )
        if vertices and vertices[-1] != ordered[0]:
            return _incomplete_edge(
                index,
                edge,
                "Connected centerlines meet through a pad or via without one exact route vertex",
                track_path,
            )
        if not vertices:
            vertices.append(ordered[0])
        vertices.append(ordered[1])
        length_nm += _rounded_segment_length_nm(*ordered)
    return PcbSwitchingLoopRouteEdgeCoverage(
        edge_index=index,
        from_pad=edge.from_pad,
        to_pad=edge.to_pad,
        kind=edge.kind,
        status="RESOLVED",
        track_uuids=track_path,
        vertices_nm=tuple(vertices),
        length_nm=length_nm,
    )


def _route_edge_coverage(
    index: int,
    edge: PcbSwitchingLoopEdge,
    specification: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> PcbSwitchingLoopRouteEdgeCoverage:
    endpoint_issue = _mapped_endpoint_issue(edge, specification, pads)
    if endpoint_issue is not None:
        return _incomplete_edge(index, edge, endpoint_issue)
    if edge.kind == "trace":
        return _resolve_trace_edge(index, edge, specification, snapshot, pads)
    if edge.kind == "component":
        return PcbSwitchingLoopRouteEdgeCoverage(
            edge_index=index,
            from_pad=edge.from_pad,
            to_pad=edge.to_pad,
            kind=edge.kind,
            status="DECLARED",
            issue=(
                f"Component transition {edge.component_reference} is explicitly mapped; "
                "internal component geometry is not measured"
            ),
        )
    plane_layer = edge.plane_layer
    plane_net = edge.net
    if plane_layer is None or plane_net is None:
        return _incomplete_edge(index, edge, "Plane edge is missing its explicit net or layer")
    if plane_layer.casefold() not in {item.casefold() for item in snapshot.copper_layers}:
        return _incomplete_edge(
            index, edge, "Plane edge layer is absent from the native copper stack"
        )
    zones = {(item.uuid.casefold(), item.layer.casefold()): item for item in snapshot.zones}
    source = pads[edge.from_pad.casefold()]
    target = pads[edge.to_pad.casefold()]

    def plane_islands(item: PcbPadConnectivityObservation) -> set[tuple[str, int]]:
        result: set[tuple[str, int]] = set()
        for island in item.connected_islands:
            if island.layer.casefold() != plane_layer.casefold():
                continue
            zone = zones.get((island.uuid.casefold(), island.layer.casefold()))
            if (
                zone is not None
                and zone.net is not None
                and zone.net.casefold() == plane_net.casefold()
            ):
                result.add((island.uuid.casefold(), island.island_index))
        return result

    common_islands = plane_islands(source) & plane_islands(target)
    if not common_islands:
        return _incomplete_edge(
            index,
            edge,
            "Mapped plane-edge pads do not share one observed filled-zone island",
        )
    if len(common_islands) != 1:
        return _incomplete_edge(
            index,
            edge,
            "Mapped plane-edge pads share multiple filled-zone island identities; selection is ambiguous",
        )
    zone_uuid, island_index = next(iter(common_islands))
    contour_area_twice = None
    if snapshot.schema_version in {"9", "10"}:
        zone = zones.get((zone_uuid, plane_layer.casefold()))
        island = (
            None
            if zone is None
            else next(
                (item for item in zone.filled_islands if item.island_index == island_index),
                None,
            )
        )
        if island is None:
            return _incomplete_edge(
                index,
                edge,
                "Native zone contour evidence is missing the shared filled-island identity",
            )
        contour_area_twice = _filled_island_area_twice_nm2(island)
        if contour_area_twice is None:
            return _incomplete_edge(
                index,
                edge,
                "Native filled-island contour has a non-positive net area",
            )
        limitation = "filled-island contour area is recorded, but current distribution and full loop area are not modeled"
    else:
        limitation = "zone contour geometry is not captured by this snapshot schema"
    return PcbSwitchingLoopRouteEdgeCoverage(
        edge_index=index,
        from_pad=edge.from_pad,
        to_pad=edge.to_pad,
        kind=edge.kind,
        status="DECLARED",
        plane_zone_uuid=zone_uuid,
        plane_island_index=island_index,
        plane_island_area_twice_nm2=contour_area_twice,
        issue=(
            f"Plane transition on {plane_net} / {plane_layer} shares a native filled island; "
            f"{limitation}"
        ),
    )


def _route_map_coverage(
    requirement: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> tuple[
    Literal["NOT_REQUESTED", "COMPLETE", "INCOMPLETE"],
    tuple[PcbSwitchingLoopRouteEdgeCoverage, ...],
    list[str],
]:
    if not requirement.route_edges:
        return "NOT_REQUESTED", (), []
    edges = tuple(
        _route_edge_coverage(index, edge, requirement, snapshot, pads)
        for index, edge in enumerate(requirement.route_edges)
    )
    issues = [
        f"Route edge {edge.edge_index} {edge.from_pad} to {edge.to_pad}: {edge.issue}"
        for edge in edges
        if edge.status != "RESOLVED"
    ]
    if any(edge.status != "RESOLVED" for edge in edges):
        return "INCOMPLETE", edges, issues
    return "COMPLETE", edges, []


def _entry(
    requirement: PcbSwitchingLoopRequirement, snapshot: PcbConnectivitySnapshot
) -> PcbSwitchingLoopCoverageEntry:
    pads = {item.pad.casefold(): item for item in snapshot.pads}
    area_twice, area_issues = _loop_area_twice_nm2(requirement, pads)
    plane_status, zone_uuid, island_index, plane_issues = _return_plane(requirement, snapshot, pads)
    route_status, route_edges, route_issues = _route_map_coverage(requirement, snapshot, pads)
    issues = [*area_issues, *plane_issues, *route_issues]
    exceeds = None
    if area_twice is not None and requirement.maximum_area_um2 is not None:
        exceeds = area_twice > 2 * requirement.maximum_area_um2 * 1_000_000
        if exceeds:
            issues.append(
                f"Measured pad-center polygon area exceeds the project limit of "
                f"{requirement.maximum_area_um2} um^2"
            )
    if requirement.maximum_area_um2 is None:
        issues.append(
            "No project maximum loop-area proxy is configured; review the measured geometry"
        )
    status = (
        "COMPLETE"
        if (
            area_twice is not None
            and plane_status == "CONNECTED"
            and exceeds is not True
            and route_status != "INCOMPLETE"
        )
        else "INCOMPLETE"
    )
    return PcbSwitchingLoopCoverageEntry(
        id=requirement.id,
        status=status,
        basis=requirement.basis,
        loop_pads=tuple(item.pad for item in requirement.loop_pads),
        loop_area_twice_nm2=area_twice,
        maximum_area_um2=requirement.maximum_area_um2,
        area_exceeds_limit=exceeds,
        return_net=requirement.return_net,
        return_plane_layer=requirement.return_plane_layer,
        return_plane_pads=tuple(item.pad for item in requirement.return_plane_pads),
        return_plane_status=plane_status,
        return_zone_uuid=zone_uuid,
        return_island_index=island_index,
        route_status=route_status,
        route_edges=route_edges,
        issues=tuple(issues),
    )


def pcb_switching_loop_entries(
    specification: PcbSwitchingLoopMap, snapshot: PcbConnectivitySnapshot
) -> tuple[PcbSwitchingLoopCoverageEntry, ...]:
    """Measure authored pad-center polygons and exact filled return-plane islands."""
    return tuple(_entry(item, snapshot) for item in specification.requirements)
