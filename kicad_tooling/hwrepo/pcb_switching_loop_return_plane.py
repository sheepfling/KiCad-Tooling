"""Focused switching-loop analysis: pcb switching loop return plane."""

from __future__ import annotations

from typing import Literal

from .pcb_connectivity_observations import PcbPadConnectivityObservation
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_switching_loop_models import (
    PcbSwitchingLoopRequirement,
)


def return_plane_coverage(
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
