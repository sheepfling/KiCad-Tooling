"""Native geometry and route-chain checks for switching-loop fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

from .ci_hosted_pcb_switching_loop_context import SwitchingLoopContext


def verify_switching_loop_geometry_cases(ctx: SwitchingLoopContext):
    """Verify native loop topology, reference-plane, and route-chain evidence."""
    from .hwrepo.evidence import digest
    from .hwrepo.pcb_reference_plane_models import (
        PcbReferencePlaneMap,
        PcbReferencePlaneRequirement,
    )
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_path_capture import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )
    from .hwrepo.pcb_switching_loop_models import (
        PcbSwitchingLoopEdge,
        PcbSwitchingLoopMap,
        PcbSwitchingLoopPad,
        PcbSwitchingLoopRequirement,
    )
    from .hwrepo.pcb_switching_loops import pcb_switching_loop_entries

    def mapped_pad(reference: str, footprint: str, net: str) -> PcbSwitchingLoopPad:
        return PcbSwitchingLoopPad(pad=reference, footprint=footprint, net=net)

    for case_name, fixture_name, plane_layer, expected_plane, test_area_limit in ctx.cases:
        case_root = ctx.scratch / case_name
        case_root.mkdir()
        relative_project = (case_root.relative_to(ctx.root) / "switching-loop.kicad_pro").as_posix()
        board = ctx.root / Path(relative_project).with_suffix(".kicad_pcb")
        shutil.copyfile(ctx.fixture_root / fixture_name, board)
        if case_name in {"front-plane", "arc-trace"}:
            source = board.read_text(encoding="utf-8")
            original = '  (segment (start 10 10) (end 25 10) (width 0.25) (layer "F.Cu") (net 1)\n    (uuid "00000000-0000-0000-0000-000000000001"))'
            replacement = (
                '  (arc (start 10 10) (mid 17.5 5) (end 25 10) (width 0.25) (layer "F.Cu") (net 1)\n    (uuid "00000000-0000-0000-0000-000000000001"))'
                if case_name == "arc-trace"
                else '  (segment (start 10 10) (end 17.5 10) (width 0.25) (layer "F.Cu") (net 1)\n    (uuid "00000000-0000-0000-0000-000000000001"))\n  (segment (start 17.5 10) (end 25 10) (width 0.25) (layer "F.Cu") (net 1)\n    (uuid "00000000-0000-0000-0000-000000000002"))'
            )
            if source.count(original) != 1:
                raise ValueError("Synthetic route geometry source segment was not unique")
            board.write_text(source.replace(original, replacement), encoding="utf-8")
        source_hash = digest(board)
        fixture_config = ctx.config.model_copy(update={"project": relative_project})
        requirement = PcbSwitchingLoopRequirement(
            id=f"synthetic-{case_name}",
            basis="Synthetic native fixture; pad-center area is a geometry measurement only",
            loop_pads=(
                mapped_pad("U1.1", "Synthetic:IC_QFN", "VDD"),
                mapped_pad("C1.1", "Synthetic:Cap_0603", "VDD"),
                mapped_pad("C1.2", "Synthetic:Cap_0603", "GND"),
                mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
            ),
            return_net="GND",
            return_plane_layer=plane_layer,
            return_plane_pads=(
                mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                mapped_pad("C1.2", "Synthetic:Cap_0603", "GND"),
            ),
            maximum_area_um2=1000000,
        )
        valid_map = PcbSwitchingLoopMap(
            basis=f"Synthetic native {case_name} return-plane regression",
            requirements=(requirement,),
        )
        trace_map = None
        if case_name in {"front-plane", "arc-trace"}:
            trace_map = PcbSwitchingLoopMap(
                basis="Synthetic native trace geometry resolver regression",
                requirements=(
                    PcbSwitchingLoopRequirement(
                        id="synthetic-native-route-chain",
                        basis="Synthetic mapped pads with native trace geometry",
                        loop_pads=(
                            mapped_pad("U1.1", "Synthetic:IC_QFN", "VDD"),
                            mapped_pad("C2.1", "Synthetic:Cap_0603", "VDD"),
                            mapped_pad("C2.2", "Synthetic:Cap_0603", "GND"),
                            mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                        ),
                        return_net="GND",
                        return_plane_layer="F.Cu",
                        return_plane_pads=(
                            mapped_pad("C2.2", "Synthetic:Cap_0603", "GND"),
                            mapped_pad("U1.2", "Synthetic:IC_QFN", "GND"),
                        ),
                        route_edges=(
                            PcbSwitchingLoopEdge(
                                from_pad="U1.1",
                                to_pad="C2.1",
                                kind="trace",
                                net="VDD",
                                layers=("F.Cu",),
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C2.1",
                                to_pad="C2.2",
                                kind="component",
                                component_reference="C2",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C2.2",
                                to_pad="U1.2",
                                kind="plane",
                                net="GND",
                                plane_layer="F.Cu",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="U1.2",
                                to_pad="U1.1",
                                kind="component",
                                component_reference="U1",
                            ),
                        ),
                    ),
                ),
            )
        over_limit = PcbSwitchingLoopMap(
            basis="Synthetic one-square-micrometre-under boundary fault",
            requirements=(requirement.model_copy(update={"maximum_area_um2": 999999}),),
        )
        try:
            retained_snapshot = None
            retained_reference_measurement: tuple[str, str, str, int, int, bool] | None = None
            native_hole_ring_count = 0
            native_clearance_hole_bounds_nm = "NOT_TESTED"
            for repeat in ("first", "repeat"):
                receipt = case_root / f"receipt-{repeat}"
                (command, snapshot) = capture_native_pcb_connectivity(
                    ctx.root, fixture_config, receipt
                )
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native switching-loop fixture command failed: {command.stderr or command.error}"
                    )
                if not native_pcb_command_matches(command, fixture_config):
                    raise ValueError(
                        "Native switching-loop fixture did not use the pinned read-only probe command"
                    )
                if snapshot is None:
                    raise ValueError(
                        "Native switching-loop fixture returned no connectivity snapshot"
                    )
                stack = {layer.casefold() for layer in snapshot.copper_layers}
                if (
                    snapshot.schema_version not in {"10", "11", "12"}
                    or snapshot.board_sha256 != source_hash
                    or snapshot.kicad_version != ctx.config.kicad_version
                    or (snapshot.image != ctx.config.image)
                    or (snapshot.probe_sha256 != expected_probe_sha256())
                    or (not snapshot.zones_refilled)
                    or (not snapshot.copper_layers)
                    or (snapshot.copper_layers[0].casefold() != "f.cu")
                    or (snapshot.copper_layers[-1].casefold() != "b.cu")
                    or (plane_layer.casefold() not in stack)
                ):
                    raise ValueError(
                        "Native switching-loop evidence is not bound to its exact source and copper stack"
                    )
                if case_name == "inner-plane":
                    matching_zones = tuple(
                        item
                        for item in snapshot.zones
                        if item.layer.casefold() == plane_layer.casefold()
                        and item.net is not None
                        and (item.net.casefold() == "gnd")
                    )
                    if len(matching_zones) != 1 or len(matching_zones[0].filled_islands) != 1:
                        raise ValueError(
                            "Native inner-plane fixture does not expose its one expected GND island"
                        )
                    outline = matching_zones[0].filled_islands[0].outline_nm
                    bounds = (
                        min(point[0] for point in outline),
                        min(point[1] for point in outline),
                        max(point[0] for point in outline),
                        max(point[1] for point in outline),
                    )
                    if bounds != (8000000, 8000000, 14000000, 14000000):
                        raise ValueError(
                            "Native inner-plane contour bounds differ from the synthetic 6 mm square"
                        )
                    test_pad = next(
                        (item for item in snapshot.pads if item.pad.casefold() == "tp1.1"), None
                    )
                    if (
                        test_pad is None
                        or test_pad.positions_nm != ((13000000, 13000000),)
                        or test_pad.net is None
                        or (test_pad.net.casefold() != "vdd")
                        or test_pad.connected_islands
                        or test_pad.connected_zones
                    ):
                        raise ValueError(
                            "Native hole-control pad differs from the synthetic isolated VDD pad"
                        )
                    hole_rings = tuple(
                        hole for item in matching_zones[0].filled_islands for hole in item.holes_nm
                    )
                    native_hole_ring_count = len(hole_rings)
                    clearance_hole_bounds = tuple(
                        (
                            min((point[0] for point in hole)),
                            min(point[1] for point in hole),
                            max(point[0] for point in hole),
                            max(point[1] for point in hole),
                        )
                        for hole in hole_rings
                    )
                    expected_clearance_hole = (12399500, 12399500, 13600500, 13600500)
                    if clearance_hole_bounds.count(expected_clearance_hole) != 1:
                        raise ValueError(
                            "Native inner-plane contour did not retain the exact VDD pad clearance ring"
                        )
                    native_clearance_hole_bounds_nm = ",".join(
                        str(value) for value in expected_clearance_hole
                    )
                pads = {item.pad.casefold(): item for item in snapshot.pads}
                expected_centers = {
                    "u1.1": ((10000000, 10000000),),
                    "c1.1": ((11000000, 10000000),),
                    "c1.2": ((11000000, 11000000),),
                    "u1.2": ((10000000, 11000000),),
                }
                if any(
                    pads[name].positions_nm != centers
                    for (name, centers) in expected_centers.items()
                ):
                    raise ValueError(
                        "Native switching-loop pad centers differ from the fixture geometry"
                    )
                tracks = tuple(sorted(snapshot.tracks, key=lambda item: item.start_nm))
                if case_name == "front-plane":
                    if (
                        len(tracks) != 2
                        or tracks[0].geometry_kind != "segment"
                        or tracks[0].start_pads != ("U1.1",)
                        or tracks[0].end_pads
                        or tracks[0].start_vias
                        or tracks[0].end_vias
                        or tracks[0].start_tracks
                        or (tracks[0].end_tracks != (tracks[1].uuid,))
                        or (tracks[1].geometry_kind != "segment")
                        or tracks[1].start_pads
                        or (tracks[1].end_pads != ("C2.1",))
                        or tracks[1].start_vias
                        or tracks[1].end_vias
                        or (tracks[1].start_tracks != (tracks[0].uuid,))
                        or tracks[1].end_tracks
                    ):
                        raise ValueError(
                            "Native track endpoint and same-layer adjacency evidence differs from the synthetic connected chain"
                        )
                elif case_name == "arc-trace":
                    if (
                        len(tracks) != 1
                        or tracks[0].geometry_kind != "arc"
                        or tracks[0].start_pads != ("U1.1",)
                        or (tracks[0].end_pads != ("C2.1",))
                        or tracks[0].start_vias
                        or tracks[0].end_vias
                        or tracks[0].start_tracks
                        or tracks[0].end_tracks
                    ):
                        raise ValueError(
                            "Native arc endpoint evidence differs from the synthetic board"
                        )
                elif len(tracks) != 1 or (
                    tracks[0].geometry_kind != "segment"
                    or tracks[0].start_pads != ("U1.1",)
                    or tracks[0].end_pads != ("C2.1",)
                    or tracks[0].start_vias
                    or tracks[0].end_vias
                    or tracks[0].start_tracks
                    or tracks[0].end_tracks
                ):
                    raise ValueError(
                        "Native track endpoint contact evidence differs from the synthetic board"
                    )
                if case_name == "inner-plane":
                    reference_requirement = PcbReferencePlaneRequirement(
                        id="synthetic-vdd-reference",
                        basis="Synthetic native signal-to-adjacent-plane coverage",
                        signal_net="VDD",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=1000,
                        minimum_referenced_fraction=0.3,
                    )
                    reference_map = PcbReferencePlaneMap(
                        basis="Synthetic inner-plane native geometry check",
                        requirements=(reference_requirement,),
                    )
                    measured = pcb_reference_plane_entries(reference_map, snapshot)
                    if (
                        len(measured) != 1
                        or measured[0].status != "COMPLETE"
                        or len(measured[0].tracks) != 1
                    ):
                        raise ValueError(
                            f"Native reference-plane measurement is incomplete: {measured}"
                        )
                    measurement = measured[0].tracks[0]
                    expected_measurement = (
                        measurement.track_uuid,
                        measurement.signal_layer,
                        measurement.reference_layer,
                        measurement.covered_fraction_numerator,
                        measurement.covered_fraction_denominator,
                        measurement.below_minimum,
                    )
                    if expected_measurement[1:] != ("F.Cu", "In1.Cu", 4, 15, True):
                        raise ValueError(
                            f"Native inner-plane centerline coverage differs from the 4/15 synthetic fault: {expected_measurement}"
                        )
                    control_map = reference_map.model_copy(
                        update={
                            "requirements": (
                                reference_requirement.model_copy(
                                    update={"minimum_referenced_fraction": 0.25}
                                ),
                            )
                        }
                    )
                    control = pcb_reference_plane_entries(control_map, snapshot)
                    if control[0].tracks[0].below_minimum:
                        raise ValueError(
                            "Native inner-plane 4/15 coverage did not pass its 0.25 control"
                        )
                    if retained_reference_measurement is None:
                        retained_reference_measurement = expected_measurement
                    elif retained_reference_measurement != expected_measurement:
                        raise ValueError(
                            "Repeated native reference-plane measurement changed for identical inputs"
                        )
                valid = pcb_switching_loop_entries(valid_map, snapshot)
                if (
                    len(valid) != 1
                    or valid[0].loop_area_twice_nm2 != 2000000000000
                    or valid[0].area_exceeds_limit is not False
                    or (valid[0].return_plane_status != expected_plane)
                    or (valid[0].return_plane_layer != plane_layer)
                ):
                    raise ValueError(f"Native switching-loop result changed: {valid}")
                expected_status = "COMPLETE" if expected_plane == "CONNECTED" else "INCOMPLETE"
                if valid[0].status != expected_status:
                    raise ValueError(
                        f"Native switching-loop coverage differs from {expected_status}: {valid[0]}"
                    )
                if expected_plane == "CONNECTED" and (not valid[0].return_zone_uuid):
                    raise ValueError("Connected native return-plane result has no zone identity")
                if expected_plane == "SPLIT" and valid[0].return_zone_uuid is not None:
                    raise ValueError("Split native return-plane result unexpectedly names one zone")
                if test_area_limit:
                    fault = pcb_switching_loop_entries(over_limit, snapshot)
                    if (
                        len(fault) != 1
                        or fault[0].status != "INCOMPLETE"
                        or fault[0].area_exceeds_limit is not True
                    ):
                        raise ValueError(f"Native loop-area threshold fault changed: {fault}")
                resolved_trace_length_nm: int | str | None = None
                measured_plane_area_twice_nm2: int | None = None
                if trace_map is not None:
                    trace_entries = pcb_switching_loop_entries(trace_map, snapshot)
                    if len(trace_entries) != 1:
                        raise ValueError("Native route-chain map did not return one coverage entry")
                    trace_entry = trace_entries[0]
                    if case_name == "arc-trace":
                        if (
                            trace_entry.route_status != "INCOMPLETE"
                            or trace_entry.route_edges[0].status != "INCOMPLETE"
                            or trace_entry.route_edges[0].track_uuids
                            != tuple(item.uuid for item in tracks)
                            or (trace_entry.route_edges[0].length_nm is not None)
                            or (trace_entry.route_edges[0].issue is None)
                            or ("unsupported arc geometry" not in trace_entry.route_edges[0].issue)
                        ):
                            raise ValueError(
                                f"Native arc trace was not conservatively reported as unsupported: {trace_entry}"
                            )
                        resolved_trace_length_nm = "UNSUPPORTED_ARC"
                    elif (
                        trace_entry.route_status != "INCOMPLETE"
                        or trace_entry.route_edges[0].status != "RESOLVED"
                        or trace_entry.route_edges[0].track_uuids
                        != tuple(item.uuid for item in tracks)
                        or (
                            trace_entry.route_edges[0].vertices_nm
                            != ((10000000, 10000000), (17500000, 10000000), (25000000, 10000000))
                        )
                        or (trace_entry.route_edges[0].length_nm != 15000000)
                        or (
                            not any(
                                "component geometry is not measured" in item
                                for item in trace_entry.issues
                            )
                        )
                    ):
                        raise ValueError(
                            f"Native trace route resolution differs from the synthetic map: {trace_entry}"
                        )
                    else:
                        resolved_trace_length_nm = trace_entry.route_edges[0].length_nm
                    plane_edge = trace_entry.route_edges[2]
                    if (
                        plane_edge.status != "DECLARED"
                        or plane_edge.plane_zone_uuid is None
                        or plane_edge.plane_island_index is None
                        or (plane_edge.plane_island_area_twice_nm2 is None)
                        or (plane_edge.plane_island_area_twice_nm2 <= 0)
                    ):
                        raise ValueError(
                            "Native plane route edge lacks exact filled-island contour evidence"
                        )
                    measured_plane_area_twice_nm2 = plane_edge.plane_island_area_twice_nm2
                if retained_snapshot is None:
                    retained_snapshot = snapshot
                elif retained_snapshot != snapshot:
                    raise ValueError(
                        "Repeated native switching-loop evidence changed for identical inputs"
                    )
            ctx.log.event(
                f"pcb-switching-loop-fixture/{case_name}",
                "PASS",
                project=ctx.project,
                kicad_version=ctx.config.kicad_version,
                fixture_sha256=source_hash,
                measured_area_twice_nm2=2000000000000,
                resolved_trace_length_nm="NOT_TESTED"
                if resolved_trace_length_nm is None
                else resolved_trace_length_nm,
                plane_contour_area_twice_nm2="NOT_TESTED"
                if measured_plane_area_twice_nm2 is None
                else measured_plane_area_twice_nm2,
                native_hole_ring_count=native_hole_ring_count,
                clearance_hole_bounds_nm=native_clearance_hole_bounds_nm,
                return_plane_layer=plane_layer,
                return_plane_status=expected_plane,
                exact_area_boundary="PASS" if test_area_limit else "NOT_TESTED",
                lower_area_fault="PASS" if test_area_limit else "NOT_TESTED",
                repeatable="true",
                receipt=(case_root.relative_to(ctx.root) / "receipt-first").as_posix(),
            )
            if case_name == "inner-plane":
                if retained_reference_measurement is None:
                    raise ValueError("Native reference-plane measurement was not retained")
                ctx.log.event(
                    "pcb-reference-plane-fixture/inner-plane",
                    "PASS",
                    project=ctx.project,
                    kicad_version=ctx.config.kicad_version,
                    fixture_sha256=source_hash,
                    signal_layer=retained_reference_measurement[1],
                    reference_layer=retained_reference_measurement[2],
                    covered_fraction=f"{retained_reference_measurement[3]}/{retained_reference_measurement[4]}",
                    fault_threshold=0.3,
                    control_threshold=0.25,
                    below_fault_threshold=str(retained_reference_measurement[5]).lower(),
                    repeatable="true",
                    receipt=(case_root.relative_to(ctx.root) / "receipt-first").as_posix(),
                )
        except Exception as exc:
            ctx.log.event(
                f"pcb-switching-loop-fixture/{case_name}",
                "FAIL",
                project=ctx.project,
                kicad_version=ctx.config.kicad_version,
                fixture_sha256=source_hash,
                error=str(exc),
            )
            raise
