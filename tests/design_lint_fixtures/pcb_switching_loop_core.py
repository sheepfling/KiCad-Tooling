"""Synthetic switching-loop inputs for focused regression suites."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopPad,
    PcbSwitchingLoopRequirement,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)

IMAGE = "ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64
PLANE_UUID = "00000000-0000-0000-0000-000000000001"
PLANE_UUID_2 = "00000000-0000-0000-0000-000000000002"


def loop_pad(reference: str, footprint: str, net: str) -> PcbSwitchingLoopPad:
    return PcbSwitchingLoopPad(pad=reference, footprint=footprint, net=net)


def requirement(*, maximum_area_um2: int | None = 150_000, layer: str = "B.Cu"):
    return PcbSwitchingLoopRequirement(
        id="synthetic-input-loop",
        basis="Synthetic switching topology and exact pad mapping",
        loop_pads=(
            loop_pad("U1.1", "Synthetic:IC_QFN", "VDD"),
            loop_pad("C1.1", "Synthetic:Cap_0603", "VDD"),
            loop_pad("C1.2", "Synthetic:Cap_0603", "GND"),
            loop_pad("U1.2", "Synthetic:IC_QFN", "GND"),
        ),
        return_net="GND",
        return_plane_layer=layer,
        return_plane_pads=(
            loop_pad("U1.2", "Synthetic:IC_QFN", "GND"),
            loop_pad("C1.2", "Synthetic:Cap_0603", "GND"),
        ),
        maximum_area_um2=maximum_area_um2,
    )


def mapping(item: PcbSwitchingLoopRequirement | None = None) -> PcbSwitchingLoopMap:
    return PcbSwitchingLoopMap(
        basis="Synthetic project-owned switching-loop review",
        requirements=(item or requirement(),),
    )


def snapshot(
    *,
    expanded: bool = False,
    split_plane: bool = False,
    copper_layers: tuple[str, ...] = ("F.Cu", "In1.Cu", "B.Cu"),
    plane_layer: str = "B.Cu",
) -> PcbConnectivitySnapshot:
    cap_x = 10_000_000 if expanded else 1_000_000
    plane_assignments = (
        {"U1.2": (PLANE_UUID, 0), "C1.2": (PLANE_UUID_2, 0)}
        if split_plane
        else {"U1.2": (PLANE_UUID, 0), "C1.2": (PLANE_UUID, 0)}
    )
    positions = {
        "U1.1": (0, 0),
        "C1.1": (cap_x, 0),
        "C1.2": (cap_x, 100_000),
        "U1.2": (0, 100_000),
    }
    pads: list[PcbPadConnectivityObservation] = []
    for reference, net, footprint in (
        ("U1.1", "VDD", "Synthetic:IC_QFN"),
        ("C1.1", "VDD", "Synthetic:Cap_0603"),
        ("C1.2", "GND", "Synthetic:Cap_0603"),
        ("U1.2", "GND", "Synthetic:IC_QFN"),
    ):
        if net == "VDD":
            connected_pads = ("U1.1", "C1.1")
            zone = None
        else:
            connected_pads = (reference,) if split_plane else ("C1.2", "U1.2")
            uuid, island_index = plane_assignments[reference]
            zone = (uuid, island_index)
        pads.append(
            PcbPadConnectivityObservation(
                pad=reference,
                net=net,
                footprint=footprint,
                dnp=False,
                connected_pads=connected_pads,
                connected_zones=(
                    () if zone is None else (PcbZoneIdentity(uuid=zone[0], layer=plane_layer),)
                ),
                connected_islands=(
                    ()
                    if zone is None
                    else (
                        PcbZoneIslandIdentity(
                            uuid=zone[0], layer=plane_layer, island_index=zone[1]
                        ),
                    )
                ),
                connected_vias=(),
                positions_nm=(positions[reference],),
            )
        )
    zone_uuids = (PLANE_UUID, PLANE_UUID_2) if split_plane else (PLANE_UUID,)
    zones = tuple(
        PcbZoneObservation(
            uuid=uuid,
            layer=plane_layer,
            name=f"Synthetic return plane {index}",
            net="GND",
            filled_island_count=1,
            unanchored_pad_island_indexes=(),
        )
        for index, uuid in enumerate(zone_uuids)
    )
    return PcbConnectivitySnapshot(
        schema_version="7",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=tuple(pads),
        net_ties=(),
        zones=zones,
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=copper_layers,
    )
