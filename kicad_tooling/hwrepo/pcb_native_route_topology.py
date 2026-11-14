"""Resolve exact source-bound pad-to-pad copper paths from native PCB evidence."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from math import isqrt

from .pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbTrackObservation,
)
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_native_route_models import PcbNativeRoutePath


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


@dataclass(frozen=True, slots=True)
class _TrackEndpointObservation:
    point_nm: tuple[int, int]
    pad_references: tuple[str, ...]
    via_ids: tuple[str, ...]
    connected_track_ids: tuple[str, ...]


def _endpoint_records(track: PcbTrackObservation) -> tuple[_TrackEndpointObservation, ...]:
    return (
        _TrackEndpointObservation(
            point_nm=track.start_nm,
            pad_references=track.start_pads,
            via_ids=track.start_vias,
            connected_track_ids=track.start_tracks,
        ),
        _TrackEndpointObservation(
            point_nm=track.end_nm,
            pad_references=track.end_pads,
            via_ids=track.end_vias,
            connected_track_ids=track.end_tracks,
        ),
    )


def _rounded_segment_length_nm(first: tuple[int, int], second: tuple[int, int]) -> int:
    squared = (second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2
    floor = isqrt(squared)
    return floor + (4 * squared >= (2 * floor + 1) ** 2)


def _bridge_track_ids(graph: Mapping[str, list[tuple[str, str]]]) -> set[str]:
    """Return route edges whose removal disconnects their endpoint vertices."""
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parents: dict[str, tuple[str, str] | None] = {}
    bridges: set[str] = set()
    next_order = 0

    for root in sorted(graph):
        if root in discovery:
            continue
        discovery[root] = next_order
        low[root] = next_order
        next_order += 1
        parents[root] = None
        pending: list[tuple[str, str | None, Iterator[tuple[str, str]]]] = [
            (root, None, iter(sorted(graph[root], key=lambda edge: (edge[1], edge[0]))))
        ]
        while pending:
            node, parent_edge, neighbors = pending[-1]
            try:
                neighbor, track_id = next(neighbors)
            except StopIteration:
                pending.pop()
                parent = parents[node]
                if parent is not None:
                    parent_node, parent_track = parent
                    low[parent_node] = min(low[parent_node], low[node])
                    if low[node] > discovery[parent_node]:
                        bridges.add(parent_track)
                continue
            if track_id == parent_edge:
                continue
            if neighbor not in discovery:
                parents[neighbor] = (node, track_id)
                discovery[neighbor] = next_order
                low[neighbor] = next_order
                next_order += 1
                pending.append(
                    (
                        neighbor,
                        track_id,
                        iter(sorted(graph.get(neighbor, ()), key=lambda edge: (edge[1], edge[0]))),
                    )
                )
            else:
                low[node] = min(low[node], discovery[neighbor])
    return bridges


def _incomplete(issue: str, tracks: tuple[str, ...] = ()) -> PcbNativeRoutePath:
    return PcbNativeRoutePath(status="INCOMPLETE", track_uuids=tracks, issue=issue)


def resolve_native_pad_route(
    *,
    net: str,
    from_pad: str,
    to_pad: str,
    layers: tuple[str, ...],
    snapshot: PcbConnectivitySnapshot,
    pads: Mapping[str, PcbPadConnectivityObservation] | None = None,
    expected_footprints: Mapping[str, str] | None = None,
    require_branch_free: bool = True,
) -> PcbNativeRoutePath:
    """Measure a unique mapped route, preserving ambiguous topology as incomplete evidence.

    ``require_branch_free`` retains the stricter component-wide topology policy used by
    checks that need a branch-free network. When false, off-path branches are allowed
    only if every edge on the mapped endpoint path is a graph bridge.
    """
    pad_map = pads or {item.pad.casefold(): item for item in snapshot.pads}
    expected = {key.casefold(): value for key, value in (expected_footprints or {}).items()}
    for reference in (from_pad, to_pad):
        item = pad_map.get(reference.casefold())
        if item is None:
            return _incomplete(
                f"Mapped edge pad {reference} is absent from the native PCB inventory"
            )
        if item.net is None or item.net.casefold() != net.casefold():
            return _incomplete(f"Mapped edge pad {reference} is not assigned to net {net!r}")
        if (
            expected.get(reference.casefold()) is not None
            and item.footprint != expected[reference.casefold()]
        ):
            return _incomplete(
                f"Mapped edge pad {reference} uses footprint {item.footprint!r}; "
                f"expected {expected[reference.casefold()]!r}"
            )
        if item.dnp:
            return _incomplete(f"Mapped edge pad {reference} is marked do-not-populate")
        if len(item.positions_nm) != 1:
            return _incomplete(f"Mapped edge pad {reference} needs exactly one native center")

    if snapshot.schema_version not in {
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
    }:
        return _incomplete("Native track endpoint-contact evidence requires PCB snapshot schema 8+")
    allowed_layers = {layer.casefold() for layer in layers}
    copper_layers = {layer.casefold() for layer in snapshot.copper_layers}
    if not allowed_layers or not allowed_layers <= copper_layers:
        return _incomplete("Trace path declares an empty or unavailable copper-layer scope")

    tracks_by_id = {item.uuid.casefold(): item for item in snapshot.tracks}
    candidates = {
        item.uuid.casefold(): item
        for item in snapshot.tracks
        if item.net is not None
        and item.net.casefold() == net.casefold()
        and item.layer.casefold() in allowed_layers
    }
    if not candidates:
        return _incomplete("No native track is observed in the declared net/layer scope")

    union = _RouteUnion()
    pads_by_node: dict[str, set[str]] = {}
    for track in candidates.values():
        for side, endpoint in zip(("start", "end"), _endpoint_records(track), strict=True):
            node = _endpoint_node(track.uuid, side)
            union.add(node)
            for reference in endpoint.pad_references:
                pad_node = f"pad:{reference.casefold()}"
                union.join(node, pad_node)
                pads_by_node.setdefault(pad_node, set()).add(reference)
            for via_id in endpoint.via_ids:
                union.join(node, f"via:{via_id}")
            for neighbor_id in endpoint.connected_track_ids:
                neighbor = tracks_by_id.get(neighbor_id.casefold())
                if neighbor is None:
                    return _incomplete("Native endpoint adjacency refers to an absent track")
                if (
                    neighbor.net is None
                    or neighbor.net.casefold() != net.casefold()
                    or neighbor.layer.casefold() not in allowed_layers
                ):
                    return _incomplete(
                        "A native track connected at this endpoint lies outside the declared net/layer scope"
                    )
                matches = tuple(
                    (neighbor_side, neighbor_endpoint)
                    for neighbor_side, neighbor_endpoint in zip(
                        ("start", "end"), _endpoint_records(neighbor), strict=True
                    )
                    if neighbor_endpoint.point_nm == endpoint.point_nm
                    and track.uuid.casefold()
                    in {value.casefold() for value in neighbor_endpoint.connected_track_ids}
                )
                if len(matches) != 1:
                    return _incomplete(
                        "Native connected-track evidence does not resolve to one matching endpoint vertex"
                    )
                neighbor_side, _ = matches[0]
                union.join(node, _endpoint_node(neighbor.uuid, neighbor_side))

    vias_by_id = {item.id: item for item in snapshot.vias}
    for track in candidates.values():
        for endpoint in _endpoint_records(track):
            for via_id in endpoint.via_ids:
                via = vias_by_id.get(via_id)
                if via is None:
                    return _incomplete("Native endpoint refers to an absent via")
                if via.net is None or via.net.casefold() != net.casefold():
                    return _incomplete("Native endpoint via has a different net")
                if (
                    via.start_layer.casefold() not in allowed_layers
                    or via.end_layer.casefold() not in allowed_layers
                ):
                    return _incomplete(
                        "Native via layer transition exceeds the declared trace-layer scope"
                    )

    graph: dict[str, list[tuple[str, str]]] = {}
    track_roots: dict[str, tuple[str, str]] = {}
    for track in candidates.values():
        start_root = union.find(_endpoint_node(track.uuid, "start"))
        end_root = union.find(_endpoint_node(track.uuid, "end"))
        track_roots[track.uuid.casefold()] = (start_root, end_root)
        graph.setdefault(start_root, []).append((end_root, track.uuid.casefold()))
        graph.setdefault(end_root, []).append((start_root, track.uuid.casefold()))

    source_node = f"pad:{from_pad.casefold()}"
    target_node = f"pad:{to_pad.casefold()}"
    if source_node not in union.parent or target_node not in union.parent:
        return _incomplete("No native track endpoint contacts one or both mapped pads")
    source_root = union.find(source_node)
    target_root = union.find(target_node)
    if source_root == target_root:
        return _incomplete(
            "Mapped pads collapse to one native endpoint vertex without a measured track path"
        )
    parents: dict[str, str | None] = {source_root: None}
    parent_tracks: dict[str, str] = {}
    pending = deque([source_root])
    has_branch = False
    has_cycle = False
    while pending:
        node = pending.popleft()
        neighbors = sorted(graph.get(node, ()), key=lambda row: (row[1], row[0]))
        if require_branch_free:
            has_branch = has_branch or len(neighbors) > 2
        for neighbor, track_id in neighbors:
            if neighbor not in parents:
                parents[neighbor] = node
                parent_tracks[neighbor] = track_id
                pending.append(neighbor)
            elif (
                require_branch_free
                and parent_tracks.get(node) != track_id
                and parent_tracks.get(neighbor) != track_id
            ):
                has_cycle = True
    if target_root not in parents:
        return _incomplete("No native track chain connects the exact mapped pads")
    if require_branch_free and has_branch:
        return _incomplete(
            "The mapped net/layer component has a connected branch; route selection is ambiguous"
        )
    if require_branch_free and has_cycle:
        return _incomplete("More than one native track chain connects the mapped pads")
    node_path_reversed = [target_root]
    track_path_reversed: list[str] = []
    current = target_root
    while current != source_root:
        parent = parents[current]
        if parent is None:
            return _incomplete("Native route predecessor chain is incomplete")
        node_path_reversed.append(parent)
        track_path_reversed.append(parent_tracks[current])
        current = parent
    node_path = tuple(reversed(node_path_reversed))
    track_path = tuple(reversed(track_path_reversed))
    if not require_branch_free:
        bridges = _bridge_track_ids(graph)
        if any(track_id not in bridges for track_id in track_path):
            return _incomplete(
                "More than one native track chain connects the mapped pads", track_path
            )
    for node in node_path:
        connected_pads = {
            reference.casefold()
            for pad_node, references in pads_by_node.items()
            if union.find(pad_node) == node
            for reference in references
        }
        if connected_pads - {from_pad.casefold(), to_pad.casefold()}:
            return _incomplete(
                "The mapped track chain contacts another pad in the same copper path", track_path
            )

    vertices: list[tuple[int, int]] = []
    geometry_kinds: list[str] = []
    midpoints: list[tuple[int, int] | None] = []
    track_lengths: list[int] = []
    length_nm = 0
    for track_id, from_node, to_node in zip(track_path, node_path[:-1], node_path[1:], strict=True):
        track = tracks_by_id[track_id]
        start_root, end_root = track_roots[track_id]
        if from_node == start_root and to_node == end_root:
            ordered = (track.start_nm, track.end_nm)
        elif from_node == end_root and to_node == start_root:
            ordered = (track.end_nm, track.start_nm)
        else:
            return _incomplete("Resolved route order differs from native track endpoints")
        if vertices and vertices[-1] != ordered[0]:
            return _incomplete(
                "Connected centerlines meet through a pad or via without one exact route vertex",
                track_path,
            )
        if not vertices:
            vertices.append(ordered[0])
        vertices.append(ordered[1])
        if track.geometry_kind not in {"segment", "arc"}:
            return _incomplete("Resolved route track has no supported geometry kind", track_path)
        geometry_kinds.append(track.geometry_kind)
        midpoints.append(track.arc_mid_nm)
        if track.geometry_kind == "segment":
            track_length_nm = _rounded_segment_length_nm(*ordered)
        elif (
            snapshot.schema_version in {"15", "16", "17", "18", "19", "20", "21", "22", "23"}
            and track.arc_mid_nm is not None
            and track.arc_length_nm is not None
        ):
            track_length_nm = track.arc_length_nm
        else:
            return _incomplete(
                "Arc centerline length and midpoint require native PCB snapshot schema 15 or later",
                track_path,
            )
        track_lengths.append(track_length_nm)
        length_nm += track_length_nm
    return PcbNativeRoutePath(
        status="RESOLVED",
        track_uuids=track_path,
        track_geometry_kinds=tuple(geometry_kinds),  # type: ignore[arg-type]
        track_midpoints_nm=tuple(midpoints),
        track_lengths_nm=tuple(track_lengths),
        vertices_nm=tuple(vertices),
        length_nm=length_nm,
    )
