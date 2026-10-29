"""Synthetic switching-loop inputs for focused regression suites."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopRequirement,
    PcbTrackObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbFootprintPlacementObservation,
    PcbZoneFilledIslandObservation,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from tests.design_lint_fixtures.pcb_switching_loop_core import (
    PLANE_UUID_2,
    requirement,
    snapshot,
)


def routed_mapping(*, layers: tuple[str, ...] = ("F.Cu",)) -> PcbSwitchingLoopMap:
    base = requirement()
    data = base.model_dump()
    data["route_edges"] = (
        PcbSwitchingLoopEdge(
            from_pad="U1.1",
            to_pad="C1.1",
            kind="trace",
            net="VDD",
            layers=layers,
        ),
        PcbSwitchingLoopEdge(
            from_pad="C1.1",
            to_pad="C1.2",
            kind="component",
            component_reference="C1",
        ),
        PcbSwitchingLoopEdge(
            from_pad="C1.2",
            to_pad="U1.2",
            kind="plane",
            net="GND",
            plane_layer="B.Cu",
        ),
        PcbSwitchingLoopEdge(
            from_pad="U1.2",
            to_pad="U1.1",
            kind="component",
            component_reference="U1",
        ),
    )
    return PcbSwitchingLoopMap(
        basis="Synthetic switching loop with explicitly classified edge roles",
        requirements=(PcbSwitchingLoopRequirement.model_validate(data),),
    )


def route_track(
    uuid: str,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    start_pads: tuple[str, ...] = (),
    end_pads: tuple[str, ...] = (),
    start_vias: tuple[str, ...] = (),
    end_vias: tuple[str, ...] = (),
    start_tracks: tuple[str, ...] = (),
    end_tracks: tuple[str, ...] = (),
    geometry_kind: Literal["segment", "arc"] = "segment",
    arc_mid_nm: tuple[int, int] | None = None,
    arc_length_nm: int | None = None,
    layer: str = "F.Cu",
) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=uuid,
        net="VDD",
        layer=layer,
        width_nm=250_000,
        start_nm=start,
        end_nm=end,
        geometry_kind=geometry_kind,
        arc_mid_nm=arc_mid_nm,
        arc_length_nm=arc_length_nm,
        start_pads=start_pads,
        end_pads=end_pads,
        start_vias=start_vias,
        end_vias=end_vias,
        start_tracks=start_tracks,
        end_tracks=end_tracks,
    )


def routed_snapshot(
    *,
    detour: bool = False,
    branch: bool = False,
    spur: bool = False,
    disconnected: bool = False,
    arc: bool = False,
) -> PcbConnectivitySnapshot:
    base = snapshot()
    first_id = "00000000-0000-0000-0000-000000000101"
    second_id = "00000000-0000-0000-0000-000000000102"
    third_id = "00000000-0000-0000-0000-000000000103"
    midpoint = (500_000, -500_000)
    if disconnected:
        tracks = ()
    elif spur:
        spur_id = "00000000-0000-0000-0000-000000000104"
        first = route_track(
            first_id,
            (0, 0),
            midpoint,
            start_pads=("U1.1",),
            end_tracks=(second_id, spur_id),
        )
        second = route_track(
            second_id,
            midpoint,
            (1_000_000, 0),
            end_pads=("C1.1",),
            start_tracks=(first_id,),
        )
        branch_spur = route_track(
            spur_id,
            midpoint,
            (500_000, 500_000),
            start_tracks=(first_id,),
        )
        tracks = (first, second, branch_spur)
    elif branch:
        alternate_first = route_track(
            second_id,
            (0, 0),
            midpoint,
            start_pads=("U1.1",),
            start_tracks=(first_id,),
            end_tracks=(third_id,),
        )
        alternate_second = route_track(
            third_id,
            midpoint,
            (1_000_000, 0),
            end_pads=("C1.1",),
            start_tracks=(second_id,),
            end_tracks=(first_id,),
        )
        direct = route_track(
            first_id,
            (0, 0),
            (1_000_000, 0),
            start_pads=("U1.1",),
            end_pads=("C1.1",),
            start_tracks=(second_id,),
            end_tracks=(third_id,),
        )
        tracks = (direct, alternate_first, alternate_second)
    elif detour:
        first = route_track(
            first_id,
            (0, 0),
            midpoint,
            start_pads=("U1.1",),
            end_tracks=(second_id,),
        )
        second = route_track(
            second_id,
            midpoint,
            (1_000_000, 0),
            end_pads=("C1.1",),
            start_tracks=(first_id,),
            geometry_kind="arc" if arc else "segment",
        )
        tracks = (first, second)
    else:
        tracks = (
            route_track(
                first_id,
                (0, 0),
                (1_000_000, 0),
                start_pads=("U1.1",),
                end_pads=("C1.1",),
                geometry_kind="arc" if arc else "segment",
                arc_mid_nm=(500_000, -500_000) if arc else None,
                arc_length_nm=1_570_796 if arc else None,
            ),
        )
    if arc:
        from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
            PcbTouchPadClearanceObservation,
        )

        arc_zones = tuple(
            zone.model_copy(
                update={
                    "filled_islands": (
                        PcbZoneFilledIslandObservation(
                            island_index=0,
                            outline_nm=((0, 0), (1_000_000, 0), (1_000_000, 1_000_000)),
                        ),
                    )
                }
            )
            for zone in base.zones
        )
        footprints = tuple(
            PcbFootprintPlacementObservation(
                reference=reference,
                footprint=footprint,
                dnp=False,
                value=f"Synthetic {reference}",
                position_nm=positions,
                orientation_microdegrees=0,
                side="F.Cu",
            )
            for reference, footprint, positions in (
                ("U1", "Synthetic:IC_QFN", (0, 0)),
                ("C1", "Synthetic:Cap_0603", (1_000_000, 100_000)),
            )
        )
        touch_observation = PcbTouchPadClearanceObservation(
            requirement_id="arc-fixture-unmeasured-touch-clearance",
            pad="U1.1",
            expected_pad_net="VDD",
            observed_pad_net="VDD",
            reference_net="GND",
            layer="B.Cu",
            matching_zone_count=1,
            closest_zone_uuid=None,
            distance_nm=None,
            status="UNSUPPORTED_LAYER",
        )
        base = base.model_copy(update={"zones": arc_zones})
        return PcbConnectivitySnapshot.model_validate(
            {
                **base.model_dump(),
                "schema_version": "15",
                "tracks": tracks,
                "footprints": footprints,
                "rule_areas": (),
                "touch_pad_clearance_observations": (touch_observation,),
                "touch_pad_clearance_requests_sha256": "d" * 64,
            }
        )
    return PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=base.board_sha256,
        kicad_version=base.kicad_version,
        image=base.image,
        probe_sha256=base.probe_sha256,
        zones_refilled=True,
        pads=base.pads,
        net_ties=(),
        zones=base.zones,
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=base.copper_layers,
    )


def legacy_arc_snapshot() -> PcbConnectivitySnapshot:
    data = routed_snapshot(arc=True).model_dump()
    data["schema_version"] = "8"
    data.pop("touch_pad_clearance_observations")
    data.pop("touch_pad_clearance_requests_sha256")
    for track in data["tracks"]:
        track.pop("arc_mid_nm")
        track.pop("arc_length_nm")
    return PcbConnectivitySnapshot.model_validate(data)


def long_routed_snapshot(segment_count: int) -> PcbConnectivitySnapshot:
    base = snapshot()
    ids = tuple(f"00000000-0000-0000-0000-{index + 1_000:012x}" for index in range(segment_count))
    tracks = tuple(
        route_track(
            track_id,
            (index * 1_000_000 // segment_count, 0),
            ((index + 1) * 1_000_000 // segment_count, 0),
            start_pads=("U1.1",) if index == 0 else (),
            end_pads=("C1.1",) if index == segment_count - 1 else (),
            start_tracks=() if index == 0 else (ids[index - 1],),
            end_tracks=() if index == segment_count - 1 else (ids[index + 1],),
        )
        for index, track_id in enumerate(ids)
    )
    return PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=base.board_sha256,
        kicad_version=base.kicad_version,
        image=base.image,
        probe_sha256=base.probe_sha256,
        zones_refilled=True,
        pads=base.pads,
        net_ties=(),
        zones=base.zones,
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=base.copper_layers,
    )


def via_routed_snapshot() -> PcbConnectivitySnapshot:
    base = snapshot()
    via_id = "e" * 64
    first_id = "00000000-0000-0000-0000-000000000201"
    second_id = "00000000-0000-0000-0000-000000000202"
    tracks = (
        route_track(
            first_id,
            (0, 0),
            (500_000, 0),
            start_pads=("U1.1",),
            end_vias=(via_id,),
        ),
        route_track(
            second_id,
            (500_000, 0),
            (1_000_000, 0),
            end_pads=("C1.1",),
            start_vias=(via_id,),
            layer="B.Cu",
        ),
    )
    return PcbConnectivitySnapshot(
        schema_version="8",
        board_sha256=base.board_sha256,
        kicad_version=base.kicad_version,
        image=base.image,
        probe_sha256=base.probe_sha256,
        zones_refilled=True,
        pads=base.pads,
        net_ties=(),
        zones=base.zones,
        vias=(
            PcbViaObservation(
                id=via_id,
                net="VDD",
                x_nm=500_000,
                y_nm=0,
                start_layer="F.Cu",
                end_layer="B.Cu",
                diameter_nm=800_000,
                drill_nm=300_000,
                kind="through",
                multiplicity=1,
            ),
        ),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=base.copper_layers,
    )


def contoured_snapshot(*, duplicate_return_island: bool = False) -> PcbConnectivitySnapshot:
    data = routed_snapshot().model_dump()
    data["schema_version"] = "9"
    outline = ((0, 0), (4_000_000, 0), (4_000_000, 3_000_000), (0, 3_000_000))
    hole = (
        (1_000_000, 1_000_000),
        (2_000_000, 1_000_000),
        (2_000_000, 2_000_000),
        (1_000_000, 2_000_000),
    )
    island = {
        "island_index": 0,
        "outline_nm": outline,
        "holes_nm": (hole,),
    }
    zones = []
    for source in data["zones"]:
        zone = dict(source)
        zone["filled_islands"] = (island,) if zone["filled_island_count"] else ()
        zones.append(zone)
    if duplicate_return_island:
        return_zone = next(item for item in zones if item["net"] == "GND")
        duplicate = dict(return_zone)
        duplicate["uuid"] = PLANE_UUID_2
        zones.append(duplicate)
        for source in data["pads"]:
            if source["pad"] not in {"U1.2", "C1.2"}:
                continue
            source["connected_zones"] = (
                *source["connected_zones"],
                {"uuid": PLANE_UUID_2, "layer": return_zone["layer"]},
            )
            source["connected_islands"] = (
                *source["connected_islands"],
                {"uuid": PLANE_UUID_2, "layer": return_zone["layer"], "island_index": 0},
            )
    data["zones"] = tuple(zones)
    return PcbConnectivitySnapshot.model_validate(data)
