"""Focused switching-loop analysis: pcb switching loop review."""

from __future__ import annotations

from .models import (
    PcbConnectivitySnapshot,
)
from .pcb_switching_loop_geometry import loop_area_twice_nm2
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageEntry,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopRequirement,
)
from .pcb_switching_loop_return_plane import return_plane_coverage
from .pcb_switching_loop_route_coverage import route_map_coverage


def _entry(
    requirement: PcbSwitchingLoopRequirement, snapshot: PcbConnectivitySnapshot
) -> PcbSwitchingLoopCoverageEntry:
    pads = {item.pad.casefold(): item for item in snapshot.pads}
    area_twice, area_issues = loop_area_twice_nm2(requirement, pads)
    plane_status, zone_uuid, island_index, plane_issues = return_plane_coverage(
        requirement, snapshot, pads
    )
    route_status, route_edges, route_issues = route_map_coverage(requirement, snapshot, pads)
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
