"""Focused switching-loop analysis: pcb switching loop route topology."""

from __future__ import annotations

from collections import deque
from math import isqrt

from .models import (
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbTrackObservation,
)
from .pcb_switching_loop_models import (
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopRequirement,
    PcbSwitchingLoopRouteEdgeCoverage,
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


def incomplete_route_edge(
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


def mapped_endpoint_issue(
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


def resolve_switching_loop_trace_edge(
    index: int,
    edge: PcbSwitchingLoopEdge,
    specification: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> PcbSwitchingLoopRouteEdgeCoverage:
    endpoint_issue = mapped_endpoint_issue(edge, specification, pads)
    if endpoint_issue is not None:
        return incomplete_route_edge(index, edge, endpoint_issue)
    if snapshot.schema_version not in {"8", "9", "10", "11", "12"}:
        return incomplete_route_edge(
            index, edge, "Native track endpoint-contact evidence requires PCB snapshot schema 8+"
        )
    allowed_layers = {layer.casefold() for layer in edge.layers}
    copper_layers = {layer.casefold() for layer in snapshot.copper_layers}
    if not allowed_layers <= copper_layers:
        return incomplete_route_edge(
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
        return incomplete_route_edge(
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
                    return incomplete_route_edge(
                        index, edge, "Native endpoint adjacency refers to an absent track"
                    )
                if (
                    neighbor.net is None
                    or neighbor.net.casefold() != (edge.net or "").casefold()
                    or neighbor.layer.casefold() not in allowed_layers
                ):
                    return incomplete_route_edge(
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
                    return incomplete_route_edge(
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
                    return incomplete_route_edge(
                        index, edge, "Native endpoint refers to an absent via"
                    )
                if via.net is None or via.net.casefold() != (edge.net or "").casefold():
                    return incomplete_route_edge(
                        index, edge, "Native endpoint via has a different net"
                    )
                if (
                    via.start_layer.casefold() not in allowed_layers
                    or via.end_layer.casefold() not in allowed_layers
                ):
                    return incomplete_route_edge(
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
        return incomplete_route_edge(
            index, edge, "No native track endpoint contacts one or both mapped pads"
        )
    source_root = union.find(source_node)
    target_root = union.find(target_node)
    if source_root == target_root:
        return incomplete_route_edge(
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
        return incomplete_route_edge(
            index, edge, "No native track chain connects the exact mapped pads"
        )
    if has_branch:
        return incomplete_route_edge(
            index,
            edge,
            "The mapped net/layer component has a connected branch; route selection is ambiguous",
        )
    if has_cycle:
        return incomplete_route_edge(
            index, edge, "More than one native track chain connects the mapped pads"
        )
    node_path_reversed = [target_root]
    track_path_reversed: list[str] = []
    current = target_root
    while current != source_root:
        parent = parents[current]
        if parent is None:
            return incomplete_route_edge(
                index, edge, "Native route predecessor chain is incomplete"
            )
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
            return incomplete_route_edge(
                index,
                edge,
                "The mapped track chain contacts another pad in the same copper path",
                track_path,
            )

    path_tracks = tuple(tracks_by_id[track_id] for track_id in track_path)
    if any(track.geometry_kind != "segment" for track in path_tracks):
        return incomplete_route_edge(
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
            return incomplete_route_edge(
                index, edge, "Resolved route order differs from native track endpoints"
            )
        if vertices and vertices[-1] != ordered[0]:
            return incomplete_route_edge(
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
