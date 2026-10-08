"""Synthetic regression cases for project-mapped PCB reference-plane screens."""

from __future__ import annotations

import hashlib
import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneCoverageReport,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
    PcbReferencePlaneTrackMeasurement,
    PcbTrackObservation,
    PcbViaObservation,
    PcbZoneFilledIslandObservation,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_reference_planes import pcb_reference_plane_entries

RULE = "pcb.reference_plane_coverage"
IMAGE = "ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64
BOARD = "a" * 64
PROBE = "c" * 64
NETLIST = "f" * 64
ZONE_GND = "00000000-0000-0000-0000-000000000001"
ZONE_OTHER = "00000000-0000-0000-0000-000000000002"


def requirement(
    *,
    net: str = "DATA",
    layer: str = "F.Cu",
    reference_net: str = "GND",
    minimum_length_um: int = 1,
    minimum_fraction: float = 0.9,
    review_excluded_short_tracks: bool = False,
    id: str = "data-reference",
) -> PcbReferencePlaneRequirement:
    return PcbReferencePlaneRequirement(
        id=id,
        basis="Synthetic explicitly mapped signal/reference-layer review",
        signal_net=net,
        signal_layers=(layer,),
        reference_net=reference_net,
        minimum_track_length_um=minimum_length_um,
        minimum_referenced_fraction=minimum_fraction,
        review_excluded_short_tracks=review_excluded_short_tracks,
    )


def mapping(*items: PcbReferencePlaneRequirement) -> PcbReferencePlaneMap:
    return PcbReferencePlaneMap(
        basis="Synthetic native copper coverage contract",
        requirements=items or (requirement(),),
    )


def zone(
    uuid: str,
    *,
    layer: str = "In1.Cu",
    net: str = "GND",
    outline: tuple[tuple[int, int], ...] = (
        (0, 0),
        (10_000_000, 0),
        (10_000_000, 10_000_000),
        (0, 10_000_000),
    ),
    holes: tuple[tuple[tuple[int, int], ...], ...] = (),
) -> PcbZoneObservation:
    return PcbZoneObservation(
        uuid=uuid,
        layer=layer,
        name=f"Synthetic {net} zone",
        net=net,
        filled_island_count=1,
        unanchored_pad_island_indexes=(0,),
        filled_islands=(
            PcbZoneFilledIslandObservation(
                island_index=0,
                outline_nm=outline,
                holes_nm=holes,
            ),
        ),
    )


def track(
    uuid_tail: str = "1",
    *,
    net: str = "DATA",
    layer: str = "F.Cu",
    start: tuple[int, int] = (0, 5_000_000),
    end: tuple[int, int] = (10_000_000, 5_000_000),
    geometry: str = "segment",
    start_vias: tuple[str, ...] = (),
    end_vias: tuple[str, ...] = (),
    start_tracks: tuple[str, ...] = (),
    end_tracks: tuple[str, ...] = (),
) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=f"00000000-0000-0000-0000-{int(uuid_tail):012d}",
        net=net,
        layer=layer,
        width_nm=250_000,
        start_nm=start,
        end_nm=end,
        geometry_kind=geometry,
        start_pads=(),
        end_pads=(),
        start_vias=start_vias,
        end_vias=end_vias,
        start_tracks=start_tracks,
        end_tracks=end_tracks,
    )


def snapshot(
    *tracks: PcbTrackObservation,
    zones: tuple[PcbZoneObservation, ...] | None = None,
    vias: tuple[PcbViaObservation, ...] = (),
    copper_layers: tuple[str, ...] = ("F.Cu", "In1.Cu", "B.Cu"),
) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        schema_version="9",
        board_sha256=BOARD,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(zone(ZONE_GND),) if zones is None else zones,
        vias=vias,
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=tracks,
        copper_layers=copper_layers,
    )


def report(specification: PcbReferencePlaneMap, observed: PcbConnectivitySnapshot):
    entries = pcb_reference_plane_entries(specification, observed)
    return PcbReferencePlaneCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=observed.board_sha256,
        snapshot_path="build/design-lint/snapshot.json",
        snapshot_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=observed.probe_sha256,
        kicad_version=observed.kicad_version,
        image=observed.image,
        netlist_sha256=NETLIST,
        entries=entries,
    )


def coach() -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-plane",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256=NETLIST,
    )


class PcbReferencePlaneTests(unittest.TestCase):
    def test_narrow_midtrace_void_between_two_mm_samples_is_reviewed(self) -> None:
        via_id = "d" * 64
        via = PcbViaObservation(
            id=via_id,
            net="DATA",
            x_nm=10_000_000,
            y_nm=13_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=800_000,
            drill_nm=300_000,
            kind="through",
            multiplicity=1,
        )
        via_clearance = (
            (9_400_000, 12_400_000),
            (10_600_000, 12_400_000),
            (10_600_000, 13_600_000),
            (9_400_000, 13_600_000),
        )
        control_outline = (
            (8_000_000, 8_000_000),
            (14_000_000, 8_000_000),
            (14_000_000, 14_000_000),
            (8_000_000, 14_000_000),
        )
        fault_outline = (
            (8_000_000, 8_000_000),
            (14_000_000, 8_000_000),
            (14_000_000, 14_000_000),
            (11_100_000, 14_000_000),
            (11_100_000, 12_800_000),
            (10_900_000, 12_800_000),
            (10_900_000, 14_000_000),
            (8_000_000, 14_000_000),
        )
        mapped_requirement = requirement(
            minimum_length_um=1_000,
            minimum_fraction=0.65,
        )
        spec = mapping(mapped_requirement)
        routed_track = track(
            start=(10_000_000, 13_000_000),
            end=(12_000_000, 13_000_000),
            start_vias=(via_id,),
        )
        control_source = snapshot(
            routed_track,
            zones=(
                zone(
                    ZONE_GND,
                    layer="B.Cu",
                    outline=control_outline,
                    holes=(via_clearance,),
                ),
            ),
            vias=(via,),
            copper_layers=("F.Cu", "B.Cu"),
        )
        fault_source = snapshot(
            routed_track,
            zones=(
                zone(
                    ZONE_GND,
                    layer="B.Cu",
                    outline=fault_outline,
                    holes=(via_clearance,),
                ),
            ),
            vias=(via,),
            copper_layers=("F.Cu", "B.Cu"),
        )

        control_entry = pcb_reference_plane_entries(spec, control_source)[0]
        fault_entry = pcb_reference_plane_entries(spec, fault_source)[0]
        self.assertEqual(control_entry.status, "COMPLETE")
        self.assertEqual(fault_entry.status, "COMPLETE")
        self.assertEqual(
            (
                control_entry.tracks[0].covered_fraction_numerator,
                control_entry.tracks[0].covered_fraction_denominator,
                control_entry.tracks[0].below_minimum,
            ),
            (7, 10, False),
        )
        self.assertEqual(
            (
                fault_entry.tracks[0].covered_fraction_numerator,
                fault_entry.tracks[0].covered_fraction_denominator,
                fault_entry.tracks[0].below_minimum,
            ),
            (3, 5, True),
        )
        self.assertEqual(
            fault_entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes,
            (via_id,),
        )

        control = evaluate(
            "synthetic-narrow-reference-void-control",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, control_source),
        )
        fault = evaluate(
            "synthetic-narrow-reference-void-fault",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, fault_source),
        )
        self.assertEqual(control.status, "PASS")
        self.assertEqual(fault.status, "REVIEW")
        self.assertTrue(any(item.rule_id == RULE for item in fault.findings))

    def test_hole_is_subtracted_and_exact_threshold_control_passes(self) -> None:
        hole = (
            (4_000_000, 4_000_000),
            (6_000_000, 4_000_000),
            (6_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        diagonal = track(start=(0, 0), end=(10_000_000, 10_000_000))
        fault_source = snapshot(diagonal, zones=(zone(ZONE_GND, holes=(hole,)),))
        fault = pcb_reference_plane_entries(mapping(), fault_source)[0]
        self.assertEqual(
            (
                fault.tracks[0].covered_fraction_numerator,
                fault.tracks[0].covered_fraction_denominator,
            ),
            (4, 5),
        )
        self.assertTrue(fault.tracks[0].below_minimum)

        exact_hole = (
            (4_000_000, 4_000_000),
            (5_000_000, 4_000_000),
            (5_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        control_source = snapshot(diagonal, zones=(zone(ZONE_GND, holes=(exact_hole,)),))
        control = pcb_reference_plane_entries(mapping(), control_source)[0]
        self.assertEqual(
            (
                control.tracks[0].covered_fraction_numerator,
                control.tracks[0].covered_fraction_denominator,
            ),
            (9, 10),
        )
        self.assertFalse(control.tracks[0].below_minimum)

    def test_disjoint_same_net_filled_zones_combine_on_one_layer(self) -> None:
        left = zone(
            ZONE_GND,
            outline=((0, 0), (5_000_000, 0), (5_000_000, 10_000_000), (0, 10_000_000)),
        )
        right = zone(
            ZONE_OTHER,
            outline=(
                (5_000_000, 0),
                (10_000_000, 0),
                (10_000_000, 10_000_000),
                (5_000_000, 10_000_000),
            ),
        )
        entry = pcb_reference_plane_entries(mapping(), snapshot(track(), zones=(left, right)))[0]
        self.assertEqual(entry.status, "COMPLETE")
        self.assertEqual(
            (
                entry.tracks[0].covered_fraction_numerator,
                entry.tracks[0].covered_fraction_denominator,
            ),
            (1, 1),
        )
        self.assertEqual(entry.tracks[0].reference_zone_uuids, (ZONE_GND, ZONE_OTHER))

    def test_split_reference_plane_gap_is_reviewed_and_explicit_alternate_net_passes(self) -> None:
        left = zone(
            ZONE_GND,
            outline=((0, 0), (4_000_000, 0), (4_000_000, 10_000_000), (0, 10_000_000)),
        )
        right = zone(
            ZONE_OTHER,
            outline=(
                (6_000_000, 0),
                (10_000_000, 0),
                (10_000_000, 10_000_000),
                (6_000_000, 10_000_000),
            ),
        )
        split_source = snapshot(track(), zones=(left, right))
        gnd_spec = mapping(requirement(reference_net="GND", minimum_fraction=0.9))
        gnd_entry = pcb_reference_plane_entries(gnd_spec, split_source)[0]
        self.assertEqual(
            (
                gnd_entry.tracks[0].covered_fraction_numerator,
                gnd_entry.tracks[0].covered_fraction_denominator,
            ),
            (4, 5),
        )
        self.assertTrue(gnd_entry.tracks[0].below_minimum)
        review = evaluate(
            "synthetic-split-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=gnd_spec),
            pcb_reference_plane_coverage=report(gnd_spec, split_source),
        )
        self.assertEqual(review.status, "REVIEW")
        self.assertIn(
            track().uuid,
            next(item for item in review.findings if item.rule_id == RULE).evidence[
                "below_threshold_track_uuids"
            ],
        )

        agnd_spec = mapping(requirement(reference_net="AGND", minimum_fraction=0.9))
        agnd_source = snapshot(track(), zones=(zone(ZONE_GND, net="AGND"),))
        agnd_entry = pcb_reference_plane_entries(agnd_spec, agnd_source)[0]
        self.assertEqual(
            (
                agnd_entry.tracks[0].covered_fraction_numerator,
                agnd_entry.tracks[0].covered_fraction_denominator,
            ),
            (1, 1),
        )
        control = evaluate(
            "synthetic-split-plane-alternate-domain",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=agnd_spec),
            pcb_reference_plane_coverage=report(agnd_spec, agnd_source),
        )
        self.assertEqual(control.status, "PASS")
        self.assertFalse(any(item.rule_id == RULE for item in control.findings))

    def test_branched_route_reports_only_the_branch_crossing_a_reference_gap(self) -> None:
        trunk = track("1")
        branch = track(
            "2",
            start=(5_000_000, 5_000_000),
            end=(5_000_000, 10_000_000),
            start_tracks=(trunk.uuid,),
        )
        branch_gap = (
            (4_500_000, 5_200_000),
            (5_500_000, 5_200_000),
            (5_500_000, 9_800_000),
            (4_500_000, 9_800_000),
        )
        source = snapshot(trunk, branch, zones=(zone(ZONE_GND, holes=(branch_gap,)),))
        spec = mapping(requirement(minimum_fraction=0.9))
        entry = pcb_reference_plane_entries(spec, source)[0]
        self.assertEqual(
            [
                (
                    item.track_uuid,
                    item.covered_fraction_numerator,
                    item.covered_fraction_denominator,
                    item.below_minimum,
                )
                for item in entry.tracks
            ],
            [(trunk.uuid, 1, 1, False), (branch.uuid, 2, 25, True)],
        )

        lint = evaluate(
            "synthetic-branched-route",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        self.assertEqual(lint.status, "REVIEW")
        self.assertEqual(finding.evidence["below_threshold_track_uuids"], (branch.uuid,))

        reordered = snapshot(branch, trunk, zones=(zone(ZONE_GND, holes=(branch_gap,)),))
        self.assertEqual(pcb_reference_plane_entries(spec, reordered)[0], entry)

        control_source = snapshot(
            trunk,
            branch,
            zones=(
                zone(
                    ZONE_GND,
                    holes=(
                        (
                            (7_000_000, 1_000_000),
                            (8_000_000, 1_000_000),
                            (8_000_000, 2_000_000),
                            (7_000_000, 2_000_000),
                        ),
                    ),
                ),
            ),
        )
        control = evaluate(
            "synthetic-branched-route-control",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, control_source),
        )
        self.assertEqual(control.status, "PASS")
        self.assertFalse(any(item.rule_id == RULE for item in control.findings))

    def test_signal_via_antipad_is_measured_as_uncovered_review_area(self) -> None:
        via_id = "d" * 64
        via = PcbViaObservation(
            id=via_id,
            net="DATA",
            x_nm=0,
            y_nm=5_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=400_000,
            drill_nm=200_000,
            kind="through",
            multiplicity=1,
        )
        via_clearance = (
            (0, 4_700_000),
            (600_000, 4_700_000),
            (600_000, 5_300_000),
            (0, 5_300_000),
        )
        source = snapshot(
            track(start=(0, 5_000_000), end=(1_000_000, 5_000_000), start_vias=(via_id,)),
            zones=(zone(ZONE_GND, holes=(via_clearance,)),),
            vias=(via,),
        )
        spec = mapping(requirement(minimum_fraction=0.9))
        entry = pcb_reference_plane_entries(spec, source)[0]
        self.assertEqual(entry.status, "COMPLETE")
        self.assertEqual(
            (
                entry.tracks[0].covered_fraction_numerator,
                entry.tracks[0].covered_fraction_denominator,
            ),
            (2, 5),
        )
        self.assertEqual(entry.tracks[0].endpoint_via_ids, (via_id,))
        self.assertEqual(
            entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes,
            (via_id,),
        )
        lint = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        self.assertEqual(lint.status, "REVIEW")
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        self.assertIn("do not identify which clearance created a hole", finding.message)
        self.assertEqual(finding.evidence["endpoint_via_hole_candidates"], (via_id,))

        unrelated_gap = (
            (0, 700_000),
            (500_000, 700_000),
            (500_000, 1_300_000),
            (0, 1_300_000),
        )
        exact_antipad = (
            (0, 4_900_000),
            (100_000, 4_900_000),
            (100_000, 5_100_000),
            (0, 5_100_000),
        )
        unrelated_candidate = snapshot(
            track("2", start=(0, 1_000_000), end=(1_000_000, 1_000_000)),
            track("3", start=(0, 5_000_000), end=(1_000_000, 5_000_000), start_vias=(via_id,)),
            zones=(zone(ZONE_GND, holes=(unrelated_gap, exact_antipad)),),
            vias=(via,),
        )
        unrelated_lint = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, unrelated_candidate),
        )
        unrelated_finding = next(item for item in unrelated_lint.findings if item.rule_id == RULE)
        self.assertNotIn("may be expected antipads", unrelated_finding.message)
        self.assertEqual(unrelated_finding.evidence["endpoint_via_hole_candidates"], ())

        offset_clearance = (
            (200_000, 4_700_000),
            (800_000, 4_700_000),
            (800_000, 5_300_000),
            (200_000, 5_300_000),
        )
        unrelated_hole = pcb_reference_plane_entries(
            spec,
            snapshot(
                track(
                    start=(0, 5_000_000),
                    end=(1_000_000, 5_000_000),
                    start_vias=(via_id,),
                ),
                zones=(zone(ZONE_GND, holes=(offset_clearance,)),),
                vias=(via,),
            ),
        )[0]
        self.assertEqual(
            unrelated_hole.tracks[0].covered_fraction_numerator,
            entry.tracks[0].covered_fraction_numerator,
        )
        self.assertEqual(unrelated_hole.tracks[0].endpoint_via_ids, (via_id,))
        self.assertEqual(
            unrelated_hole.tracks[0].endpoint_via_ids_with_center_in_reference_holes,
            (),
        )

    def test_merged_clearance_hole_does_not_assign_hole_ownership_to_endpoint_via(self) -> None:
        endpoint_via_id = "d" * 64
        unrelated_via_id = "e" * 64
        endpoint_via = PcbViaObservation(
            id=endpoint_via_id,
            net="DATA",
            x_nm=0,
            y_nm=5_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=400_000,
            drill_nm=200_000,
            kind="through",
            multiplicity=1,
        )
        unrelated_via = PcbViaObservation(
            id=unrelated_via_id,
            net="OTHER",
            x_nm=500_000,
            y_nm=5_000_000,
            start_layer="F.Cu",
            end_layer="B.Cu",
            diameter_nm=400_000,
            drill_nm=200_000,
            kind="through",
            multiplicity=1,
        )
        merged_hole = (
            (0, 4_700_000),
            (800_000, 4_700_000),
            (800_000, 5_300_000),
            (0, 5_300_000),
        )
        source = snapshot(
            track(
                start=(0, 5_000_000),
                end=(1_000_000, 5_000_000),
                start_vias=(endpoint_via_id,),
            ),
            zones=(zone(ZONE_GND, holes=(merged_hole,)),),
            vias=(endpoint_via, unrelated_via),
        )
        spec = mapping(requirement(minimum_fraction=0.9))
        entry = pcb_reference_plane_entries(spec, source)[0]
        self.assertEqual(
            (
                entry.tracks[0].covered_fraction_numerator,
                entry.tracks[0].covered_fraction_denominator,
            ),
            (1, 5),
        )
        self.assertEqual(
            entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes,
            (endpoint_via_id,),
        )

        lint = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        self.assertIn("do not identify which clearance created a hole", finding.message)
        self.assertIn("inspect the geometry", finding.message)
        self.assertEqual(finding.evidence["endpoint_via_hole_candidates"], (endpoint_via_id,))

    def test_only_immediately_adjacent_exact_reference_net_copper_counts(self) -> None:
        source = snapshot(
            track(),
            zones=(
                zone(ZONE_OTHER, layer="In1.Cu", net="SHIELD"),
                zone(ZONE_GND, layer="B.Cu"),
            ),
        )
        entry = pcb_reference_plane_entries(mapping(), source)[0]
        self.assertEqual(entry.status, "COMPLETE")
        self.assertEqual(len(entry.tracks), 1)
        self.assertEqual(entry.tracks[0].reference_layer, "In1.Cu")
        self.assertEqual(entry.tracks[0].reference_zone_uuids, ())
        self.assertEqual(entry.tracks[0].covered_fraction_numerator, 0)
        self.assertTrue(entry.tracks[0].below_minimum)

    def test_inner_route_needs_one_adjacent_layer_to_meet_threshold(self) -> None:
        hole = (
            (4_000_000, 4_000_000),
            (6_000_000, 4_000_000),
            (6_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        source = snapshot(
            track(layer="In1.Cu"),
            zones=(
                zone(ZONE_GND, layer="F.Cu", holes=(hole,)),
                zone(ZONE_OTHER, layer="B.Cu", net="SHIELD"),
            ),
        )
        entry = pcb_reference_plane_entries(mapping(requirement(layer="In1.Cu")), source)[0]
        self.assertEqual(
            [
                (
                    item.reference_layer,
                    item.covered_fraction_numerator,
                    item.covered_fraction_denominator,
                    item.below_minimum,
                )
                for item in entry.tracks
            ],
            [("F.Cu", 4, 5, True), ("B.Cu", 0, 1, True)],
        )

        full_source = snapshot(
            track(layer="In1.Cu"),
            zones=(zone(ZONE_GND, layer="F.Cu"),),
        )
        full_entry = pcb_reference_plane_entries(mapping(requirement(layer="In1.Cu")), full_source)[
            0
        ]
        self.assertFalse(all(item.below_minimum for item in full_entry.tracks))
        spec = mapping(requirement(layer="In1.Cu"))
        control = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, full_source),
        )
        self.assertEqual(control.status, "PASS")
        self.assertFalse(any(item.rule_id == RULE for item in control.findings))

    def test_short_segments_are_excluded_and_arcs_keep_coverage_incomplete(self) -> None:
        short = track("1", start=(0, 0), end=(999_999, 0))
        short_entry = pcb_reference_plane_entries(
            mapping(requirement(minimum_length_um=1000)), snapshot(short)
        )[0]
        self.assertEqual(short_entry.status, "INCOMPLETE")
        self.assertEqual(short_entry.excluded_short_track_uuids, (short.uuid,))
        self.assertIn("minimum segment length", short_entry.issues[0])

        arc_entry = pcb_reference_plane_entries(mapping(), snapshot(track(geometry="arc")))[0]
        self.assertEqual(arc_entry.status, "INCOMPLETE")
        self.assertIn("unsupported arc geometry", arc_entry.issues[0])
        self.assertEqual(arc_entry.tracks, ())

    def test_excluded_short_track_review_is_opt_in_and_cli_text_keeps_ids_visible(self) -> None:
        long_track = track("2", start=(0, 0), end=(5_000_000, 0))
        short_track = track("3", start=(0, 1_000_000), end=(999_999, 1_000_000))
        source = snapshot(long_track, short_track)

        quiet_spec = mapping(requirement(minimum_length_um=1000))
        quiet_entry = pcb_reference_plane_entries(quiet_spec, source)[0]
        self.assertEqual(quiet_entry.status, "COMPLETE")
        self.assertEqual(quiet_entry.excluded_short_track_uuids, (short_track.uuid,))
        quiet = evaluate(
            "synthetic-short-track-policy",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=quiet_spec),
            pcb_reference_plane_coverage=report(quiet_spec, source),
        )
        self.assertEqual(quiet.status, "PASS")
        self.assertFalse(any(item.rule_id == RULE for item in quiet.findings))
        quiet_text = text_report(quiet)
        self.assertIn("short-track review disabled", quiet_text)
        self.assertIn(short_track.uuid, quiet_text)

        review_spec = mapping(
            requirement(minimum_length_um=1000, review_excluded_short_tracks=True)
        )
        review_entry = pcb_reference_plane_entries(review_spec, source)[0]
        self.assertEqual(review_entry.status, "INCOMPLETE")
        self.assertIn("require review", review_entry.issues[0])
        reviewed = evaluate(
            "synthetic-short-track-policy",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=review_spec),
            pcb_reference_plane_coverage=report(review_spec, source),
        )
        self.assertEqual(reviewed.status, "REVIEW")
        finding = next(item for item in reviewed.findings if item.rule_id == RULE)
        self.assertEqual(finding.evidence["excluded_short_track_uuids"], (short_track.uuid,))
        self.assertEqual(finding.evidence["review_excluded_short_tracks"], ("true",))
        self.assertIn("were excluded", finding.message)
        self.assertIn("short-track review enabled", text_report(reviewed))

        blocking = evaluate(
            "synthetic-short-track-policy",
            coach(),
            DesignLintPolicy(
                pcb_reference_plane_map=review_spec,
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE,
                        mode="block",
                        reason="Synthetic test promotes excluded-route coverage",
                    ),
                ),
            ),
            pcb_reference_plane_coverage=report(review_spec, source),
        )
        self.assertEqual(blocking.status, "FAIL")

        reordered = snapshot(short_track, long_track)
        self.assertEqual(pcb_reference_plane_entries(quiet_spec, reordered)[0], quiet_entry)

    def test_unmapped_track_and_missing_stack_layer_remain_incomplete(self) -> None:
        no_tracks = pcb_reference_plane_entries(mapping(), snapshot())[0]
        self.assertEqual(no_tracks.status, "INCOMPLETE")
        self.assertIn("No native track items", no_tracks.issues[0])

        missing_layer = snapshot(track(), copper_layers=("In1.Cu", "B.Cu"))
        incomplete = pcb_reference_plane_entries(mapping(), missing_layer)[0]
        self.assertEqual(incomplete.status, "INCOMPLETE")
        self.assertIn("Mapped signal layer F.Cu is absent", incomplete.issues[0])
        self.assertTrue(
            any("no observed adjacent copper layer" in item for item in incomplete.issues)
        )

    def test_exactly_mapped_fault_is_reviewable_and_control_is_quiet(self) -> None:
        hole = (
            (4_000_000, 4_000_000),
            (6_000_000, 4_000_000),
            (6_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        spec = mapping()
        fault = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(
                spec, snapshot(track(), zones=(zone(ZONE_GND, holes=(hole,)),))
            ),
        )
        finding = next(item for item in fault.findings if item.rule_id == RULE)
        self.assertEqual(fault.status, "REVIEW")
        self.assertIn(track().uuid, finding.evidence["below_threshold_track_uuids"])
        self.assertIn("does not establish a continuous return-current path", finding.message)

        control = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, snapshot(track())),
        )
        self.assertEqual(control.status, "PASS")
        self.assertFalse(any(item.rule_id == RULE for item in control.findings))

        blocking = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(
                pcb_reference_plane_map=spec,
                rules=(
                    DesignLintRuleOverride(rule_id=RULE, mode="block", reason="synthetic gate"),
                ),
            ),
            pcb_reference_plane_coverage=report(
                spec, snapshot(track(), zones=(zone(ZONE_GND, holes=(hole,)),))
            ),
        )
        self.assertEqual(blocking.status, "FAIL")

    def test_map_scope_is_unique_and_threshold_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValidationError, "only one reference-plane screen"):
            mapping(requirement(), requirement(id="duplicate-scope"))
        with self.assertRaises(ValidationError):
            requirement(minimum_fraction=1.1)

    def test_report_rejects_unreduced_fraction_and_underlength_measurement(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must be reduced"):
            PcbReferencePlaneTrackMeasurement(
                track_uuid=track().uuid,
                signal_layer="F.Cu",
                reference_layer="In1.Cu",
                reference_zone_uuids=(),
                segment_length_nm=1_000,
                covered_fraction_numerator=2,
                covered_fraction_denominator=4,
                below_minimum=True,
            )
        measurement = PcbReferencePlaneTrackMeasurement(
            track_uuid=track().uuid,
            signal_layer="F.Cu",
            reference_layer="In1.Cu",
            reference_zone_uuids=(),
            segment_length_nm=999,
            covered_fraction_numerator=0,
            covered_fraction_denominator=1,
            below_minimum=True,
        )
        with self.assertRaisesRegex(ValidationError, "meet the authored length"):
            PcbReferencePlaneCoverageEntry(
                id="data-reference",
                status="COMPLETE",
                basis="Synthetic source-bound validation",
                signal_net="DATA",
                signal_layers=("F.Cu",),
                reference_net="GND",
                minimum_track_length_um=1,
                minimum_referenced_fraction=0.9,
                tracks=(measurement,),
            )


if __name__ == "__main__":
    unittest.main()
