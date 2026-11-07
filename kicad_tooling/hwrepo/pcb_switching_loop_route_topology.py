"""Switching-loop adapters for shared native PCB route topology."""

from __future__ import annotations

from collections.abc import Mapping

from .pcb_connectivity_observations import PcbPadConnectivityObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_native_route_topology import resolve_native_pad_route
from .pcb_switching_loop_models import (
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopRequirement,
    PcbSwitchingLoopRouteEdgeCoverage,
)


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
    pads: Mapping[str, PcbPadConnectivityObservation],
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
    pads: Mapping[str, PcbPadConnectivityObservation],
) -> PcbSwitchingLoopRouteEdgeCoverage:
    """Retain switching-loop endpoint checks around the shared exact route resolver."""
    endpoint_issue = mapped_endpoint_issue(edge, specification, pads)
    if endpoint_issue is not None:
        return incomplete_route_edge(index, edge, endpoint_issue)
    route = resolve_native_pad_route(
        net=edge.net or "",
        from_pad=edge.from_pad,
        to_pad=edge.to_pad,
        layers=edge.layers,
        snapshot=snapshot,
        pads=pads,
        expected_footprints={item.pad: item.footprint for item in specification.loop_pads},
    )
    if route.status == "INCOMPLETE":
        return incomplete_route_edge(
            index, edge, route.issue or "Native route is incomplete", route.track_uuids
        )
    return PcbSwitchingLoopRouteEdgeCoverage(
        edge_index=index,
        from_pad=edge.from_pad,
        to_pad=edge.to_pad,
        kind=edge.kind,
        status="RESOLVED",
        track_uuids=route.track_uuids,
        track_geometry_kinds=route.track_geometry_kinds,
        track_midpoints_nm=route.track_midpoints_nm,
        track_lengths_nm=route.track_lengths_nm,
        vertices_nm=route.vertices_nm,
        length_nm=route.length_nm,
    )
