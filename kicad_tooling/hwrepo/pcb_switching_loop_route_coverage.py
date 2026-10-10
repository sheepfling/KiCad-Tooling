"""Focused switching-loop analysis: pcb switching loop route coverage."""

from __future__ import annotations

from typing import Literal

from .pcb_connectivity_observations import PcbPadConnectivityObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_switching_loop_geometry import filled_island_area_twice_nm2
from .pcb_switching_loop_models import (
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopRequirement,
    PcbSwitchingLoopRouteEdgeCoverage,
)
from .pcb_switching_loop_route_topology import (
    incomplete_route_edge,
    mapped_endpoint_issue,
    resolve_switching_loop_trace_edge,
)


def _route_edge_coverage(
    index: int,
    edge: PcbSwitchingLoopEdge,
    specification: PcbSwitchingLoopRequirement,
    snapshot: PcbConnectivitySnapshot,
    pads: dict[str, PcbPadConnectivityObservation],
) -> PcbSwitchingLoopRouteEdgeCoverage:
    endpoint_issue = mapped_endpoint_issue(edge, specification, pads)
    if endpoint_issue is not None:
        return incomplete_route_edge(index, edge, endpoint_issue)
    if edge.kind == "trace":
        return resolve_switching_loop_trace_edge(index, edge, specification, snapshot, pads)
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
        return incomplete_route_edge(index, edge, "Plane edge is missing its explicit net or layer")
    if plane_layer.casefold() not in {item.casefold() for item in snapshot.copper_layers}:
        return incomplete_route_edge(
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
        return incomplete_route_edge(
            index,
            edge,
            "Mapped plane-edge pads do not share one observed filled-zone island",
        )
    if len(common_islands) != 1:
        return incomplete_route_edge(
            index,
            edge,
            "Mapped plane-edge pads share multiple filled-zone island identities; selection is ambiguous",
        )
    zone_uuid, island_index = next(iter(common_islands))
    contour_area_twice = None
    if snapshot.schema_version in {"9", "10", "11", "12"}:
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
            return incomplete_route_edge(
                index,
                edge,
                "Native zone contour evidence is missing the shared filled-island identity",
            )
        contour_area_twice = filled_island_area_twice_nm2(island)
        if contour_area_twice is None:
            return incomplete_route_edge(
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


def route_map_coverage(
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
