"""Synthetic review cases for authored switching-loop geometry proxies."""

from __future__ import annotations

import hashlib
import unittest
from typing import Literal

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbSwitchingLoopCoverageEntry,
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopPad,
    PcbSwitchingLoopRequirement,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_switching_loops import pcb_switching_loop_entries

RULE = "pcb.switching_loop_geometry"
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
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=base.copper_layers,
    )


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


def coverage(
    specification: PcbSwitchingLoopMap, observed: PcbConnectivitySnapshot
) -> PcbSwitchingLoopCoverageReport:
    entries = pcb_switching_loop_entries(specification, observed)
    return PcbSwitchingLoopCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=observed.board_sha256,
        snapshot_path="build/design-lint/switching-loop/snapshot.json",
        snapshot_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=observed.probe_sha256,
        kicad_version=observed.kicad_version,
        image=observed.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )


def coach() -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-loop",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )


class PcbSwitchingLoopTests(unittest.TestCase):
    def test_compact_loop_and_shared_multilayer_plane_pass_authored_geometry_screen(self) -> None:
        result = pcb_switching_loop_entries(mapping(), snapshot())[0]

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.loop_area_twice_nm2, 200_000_000_000)
        self.assertFalse(result.area_exceeds_limit)
        self.assertEqual(result.return_plane_status, "CONNECTED")
        self.assertEqual(result.return_zone_uuid, PLANE_UUID)
        self.assertEqual(result.return_island_index, 0)

    def test_pad_inventory_order_preserves_area_finding_and_compact_repair_clears_it(
        self,
    ) -> None:
        spec = mapping()
        expanded = snapshot(expanded=True)
        reordered_expanded = expanded.model_copy(
            update={
                "pads": tuple(
                    pad.model_copy(
                        update={
                            "connected_pads": tuple(reversed(pad.connected_pads)),
                            "connected_islands": tuple(reversed(pad.connected_islands)),
                        }
                    )
                    for pad in reversed(expanded.pads)
                )
            }
        )
        measured = coverage(spec, expanded)
        reordered_measured = coverage(spec, reordered_expanded)
        self.assertEqual(measured.entries, reordered_measured.entries)
        self.assertEqual(measured.map_sha256, reordered_measured.map_sha256)
        self.assertNotEqual(measured.snapshot_sha256, reordered_measured.snapshot_sha256)

        native = coach()
        policy = DesignLintPolicy(pcb_switching_loop_map=spec)
        original = evaluate("synthetic-loop", native, policy, pcb_switching_loop_coverage=measured)
        reordered = evaluate(
            "synthetic-loop", native, policy, pcb_switching_loop_coverage=reordered_measured
        )
        original_finding = next(item for item in original.findings if item.rule_id == RULE)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
        self.assertEqual(original.status, "REVIEW")
        self.assertEqual(
            (original_finding.subject, original_finding.fingerprint, original_finding.evidence),
            (reordered_finding.subject, reordered_finding.fingerprint, reordered_finding.evidence),
        )

        compact_measured = coverage(spec, snapshot())
        compact = evaluate(
            "synthetic-loop", native, policy, pcb_switching_loop_coverage=compact_measured
        )
        self.assertEqual(compact_measured.entries[0].status, "COMPLETE")
        self.assertFalse(any(item.rule_id == RULE for item in compact.findings))

    def test_track_inventory_order_preserves_resolved_route_finding_and_snapshot_binding(
        self,
    ) -> None:
        spec = routed_mapping(layers=("F.Cu", "B.Cu"))
        evidence = via_routed_snapshot()
        reordered_evidence = evidence.model_copy(
            update={
                "pads": tuple(reversed(evidence.pads)),
                "tracks": tuple(reversed(evidence.tracks)),
                "vias": tuple(reversed(evidence.vias)),
            }
        )
        measured = coverage(spec, evidence)
        reordered_measured = coverage(spec, reordered_evidence)
        self.assertEqual(measured.entries, reordered_measured.entries)
        self.assertEqual(measured.map_sha256, reordered_measured.map_sha256)
        self.assertNotEqual(measured.snapshot_sha256, reordered_measured.snapshot_sha256)
        self.assertEqual(measured.entries[0].route_edges[0].status, "RESOLVED")

        native = coach()
        policy = DesignLintPolicy(pcb_switching_loop_map=spec)
        original = evaluate("synthetic-loop", native, policy, pcb_switching_loop_coverage=measured)
        reordered = evaluate(
            "synthetic-loop", native, policy, pcb_switching_loop_coverage=reordered_measured
        )
        original_finding = next(item for item in original.findings if item.rule_id == RULE)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
        self.assertEqual(
            (original_finding.subject, original_finding.fingerprint, original_finding.evidence),
            (reordered_finding.subject, reordered_finding.fingerprint, reordered_finding.evidence),
        )

    def test_explicit_edge_map_resolves_trace_and_preserves_unmeasured_roles(self) -> None:
        result = pcb_switching_loop_entries(routed_mapping(), routed_snapshot())[0]

        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.route_status, "INCOMPLETE")
        self.assertEqual(
            tuple(item.status for item in result.route_edges),
            ("RESOLVED", "DECLARED", "DECLARED", "DECLARED"),
        )
        trace = result.route_edges[0]
        self.assertEqual(trace.from_pad, "U1.1")
        self.assertEqual(trace.to_pad, "C1.1")
        self.assertEqual(trace.vertices_nm, ((0, 0), (1_000_000, 0)))
        self.assertEqual(trace.length_nm, 1_000_000)
        self.assertTrue(any("component geometry is not measured" in item for item in result.issues))
        self.assertTrue(
            any("zone contour geometry is not captured" in item for item in result.issues)
        )

    def test_schema_nine_plane_edge_reports_exact_filled_contour_area(self) -> None:
        result = pcb_switching_loop_entries(routed_mapping(), contoured_snapshot())[0]
        plane_edge = result.route_edges[2]

        self.assertEqual(plane_edge.status, "DECLARED")
        self.assertEqual(plane_edge.plane_zone_uuid, PLANE_UUID)
        self.assertEqual(plane_edge.plane_island_index, 0)
        self.assertEqual(plane_edge.plane_island_area_twice_nm2, 22_000_000_000_000)
        self.assertIn("filled-island contour area is recorded", plane_edge.issue)

    def test_schema_nine_requires_valid_contours_for_every_filled_island(self) -> None:
        data = contoured_snapshot().model_dump()
        data["zones"][0].pop("filled_islands")
        with self.assertRaisesRegex(ValidationError, "requires explicit filled-island contour"):
            PcbConnectivitySnapshot.model_validate(data)

        data = contoured_snapshot().model_dump()
        data["zones"][0]["filled_islands"][0]["outline_nm"] = (
            (0, 0),
            (1_000_000, 1_000_000),
            (2_000_000, 2_000_000),
        )
        with self.assertRaisesRegex(ValidationError, "zero area"):
            PcbConnectivitySnapshot.model_validate(data)

    def test_multiple_shared_plane_islands_are_reported_as_ambiguous(self) -> None:
        result = pcb_switching_loop_entries(
            routed_mapping(), contoured_snapshot(duplicate_return_island=True)
        )[0]

        self.assertEqual(result.return_plane_status, "AMBIGUOUS")
        self.assertIsNone(result.return_zone_uuid)
        self.assertIsNone(result.return_island_index)
        plane_edge = result.route_edges[2]
        self.assertEqual(plane_edge.status, "INCOMPLETE")
        self.assertIn("selection is ambiguous", plane_edge.issue)

    def test_detour_changes_trace_measurement_while_pad_center_proxy_stays_fixed(self) -> None:
        straight = pcb_switching_loop_entries(routed_mapping(), routed_snapshot())[0]
        detoured = pcb_switching_loop_entries(routed_mapping(), routed_snapshot(detour=True))[0]

        self.assertEqual(detoured.loop_area_twice_nm2, straight.loop_area_twice_nm2)
        self.assertNotEqual(
            detoured.route_edges[0].vertices_nm, straight.route_edges[0].vertices_nm
        )
        self.assertGreater(detoured.route_edges[0].length_nm, straight.route_edges[0].length_nm)

    def test_long_trace_chain_resolves_without_recursive_search(self) -> None:
        result = pcb_switching_loop_entries(routed_mapping(), long_routed_snapshot(1_100))[0]

        self.assertEqual(result.route_edges[0].status, "RESOLVED")
        self.assertEqual(len(result.route_edges[0].track_uuids), 1_100)
        self.assertEqual(result.route_edges[0].vertices_nm[0], (0, 0))
        self.assertEqual(result.route_edges[0].vertices_nm[-1], (1_000_000, 0))
        self.assertEqual(result.route_edges[0].length_nm, 1_000_000)

    def test_multilayer_trace_joins_at_an_observed_via_and_checks_scope(self) -> None:
        observed = via_routed_snapshot()
        resolved = pcb_switching_loop_entries(routed_mapping(layers=("F.Cu", "B.Cu")), observed)[
            0
        ].route_edges[0]
        excluded_layer = pcb_switching_loop_entries(routed_mapping(), observed)[0].route_edges[0]

        self.assertEqual(resolved.status, "RESOLVED")
        self.assertEqual(
            resolved.track_uuids,
            ("00000000-0000-0000-0000-000000000201", "00000000-0000-0000-0000-000000000202"),
        )
        self.assertEqual(resolved.vertices_nm, ((0, 0), (500_000, 0), (1_000_000, 0)))
        self.assertEqual(resolved.length_nm, 1_000_000)
        self.assertEqual(excluded_layer.status, "INCOMPLETE")
        self.assertIn("via layer transition exceeds", excluded_layer.issue)

    def test_route_resolution_is_visible_in_review_finding_and_text_report(self) -> None:
        spec = routed_mapping()
        report = coverage(spec, contoured_snapshot())
        result = evaluate(
            "synthetic-loop",
            coach(),
            DesignLintPolicy(pcb_switching_loop_map=spec),
            pcb_switching_loop_coverage=report,
        )
        finding = next(item for item in result.findings if item.rule_id == RULE)

        self.assertEqual(finding.evidence["trace_route_status"], ("INCOMPLETE",))
        self.assertIn("length 1000000 nm", finding.evidence["trace_route_edges"][0])
        self.assertIn(
            "component geometry is not measured", finding.evidence["trace_route_edges"][1]
        )
        self.assertIn(
            "contour doubled area 22000000000000 nm^2",
            finding.evidence["trace_route_edges"][2],
        )
        rendered = text_report(result)
        self.assertIn("trace-route coverage INCOMPLETE", rendered)
        self.assertIn("length 1000000 nm", rendered)
        self.assertIn("contour doubled area 22000000000000 nm^2", rendered)

    def test_missing_branching_and_arc_trace_paths_are_incomplete(self) -> None:
        cases = (
            (routed_snapshot(disconnected=True), "No native track is observed"),
            (routed_snapshot(branch=True), "More than one native track chain"),
            (routed_snapshot(spur=True), "connected branch"),
            (routed_snapshot(arc=True), "unsupported arc geometry"),
        )
        for observed, expected_issue in cases:
            with self.subTest(expected_issue=expected_issue):
                result = pcb_switching_loop_entries(routed_mapping(), observed)[0]
                self.assertEqual(result.route_status, "INCOMPLETE")
                self.assertEqual(result.route_edges[0].status, "INCOMPLETE")
                self.assertIn(expected_issue, result.route_edges[0].issue)

    def test_route_contract_requires_every_cyclic_edge_in_exact_order(self) -> None:
        data = routed_mapping().requirements[0].model_dump()
        data["route_edges"] = data["route_edges"][:-1]
        with self.assertRaisesRegex(ValidationError, "cover every ordered pad edge"):
            PcbSwitchingLoopRequirement.model_validate(data)

        data = routed_mapping().requirements[0].model_dump()
        data["route_edges"] = (data["route_edges"][1], *data["route_edges"][1:])
        with self.assertRaisesRegex(ValidationError, "exact ordered pad cycle"):
            PcbSwitchingLoopRequirement.model_validate(data)

    def test_route_report_requires_the_exact_cycle_and_track_vertex_count(self) -> None:
        entry = pcb_switching_loop_entries(routed_mapping(), routed_snapshot())[0]
        data = entry.model_dump()
        data["route_edges"] = data["route_edges"][:-1]
        with self.assertRaisesRegex(ValidationError, "every edge in the ordered pad cycle"):
            PcbSwitchingLoopCoverageEntry.model_validate(data)

        data = entry.model_dump()
        data["route_edges"][0]["track_uuids"] = (
            "00000000-0000-0000-0000-000000000101",
            "00000000-0000-0000-0000-000000000102",
        )
        with self.assertRaisesRegex(ValidationError, "one more vertex than tracks"):
            PcbSwitchingLoopCoverageEntry.model_validate(data)

    def test_enlarged_loop_exceeds_project_area_limit(self) -> None:
        result = pcb_switching_loop_entries(mapping(), snapshot(expanded=True))[0]

        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(result.area_exceeds_limit)
        self.assertIn("exceeds the project limit", result.issues[0])

    def test_split_filled_return_plane_is_reported(self) -> None:
        result = pcb_switching_loop_entries(mapping(), snapshot(split_plane=True))[0]

        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.return_plane_status, "SPLIT")
        self.assertTrue(any("do not share one filled island" in item for item in result.issues))

    def test_absent_layer_is_unsupported_and_missing_stack_is_schema_error(self) -> None:
        result = pcb_switching_loop_entries(
            mapping(requirement(layer="In2.Cu")), snapshot(copper_layers=("F.Cu", "B.Cu"))
        )[0]
        self.assertEqual(result.return_plane_status, "UNSUPPORTED")
        self.assertEqual(result.status, "INCOMPLETE")

        with self.assertRaisesRegex(ValidationError, "actual copper stack"):
            PcbConnectivitySnapshot(
                schema_version="7",
                board_sha256="a" * 64,
                kicad_version="10.0.5",
                image=IMAGE,
                probe_sha256="c" * 64,
                zones_refilled=True,
                pads=(),
                net_ties=(),
                zones=(),
                vias=(),
                access_probe_observations=(),
                access_probe_requests_sha256=None,
                tracks=(),
            )

    def test_missing_threshold_emits_review_and_policy_is_configurable(self) -> None:
        spec = mapping(requirement(maximum_area_um2=None))
        report = coverage(spec, snapshot())
        policy = DesignLintPolicy(pcb_switching_loop_map=spec)
        reviewed = evaluate("synthetic-loop", coach(), policy, pcb_switching_loop_coverage=report)
        finding = next(item for item in reviewed.findings if item.rule_id == RULE)
        blocking = evaluate(
            "synthetic-loop",
            coach(),
            policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id=RULE,
                            mode="block",
                            reason="Synthetic project release requirement",
                        ),
                    )
                }
            ),
            pcb_switching_loop_coverage=report,
        )
        disabled = evaluate(
            "synthetic-loop",
            coach(),
            policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id=RULE,
                            mode="off",
                            reason="Synthetic project disposition",
                        ),
                    )
                }
            ),
            pcb_switching_loop_coverage=report,
        )
        ignored = evaluate(
            "synthetic-loop",
            coach(),
            policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=RULE,
                            fingerprint=finding.fingerprint,
                            reason="Synthetic reviewed exception",
                        ),
                    )
                }
            ),
            pcb_switching_loop_coverage=report,
        )

        self.assertEqual(reviewed.status, "REVIEW")
        self.assertEqual(blocking.status, "FAIL")
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.pcb_switching_loop.status, "DISABLED")
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")
        self.assertIn("polygon through authored pad centers", finding.message)
        self.assertEqual(finding.evidence["return_plane_status"], ("CONNECTED",))
