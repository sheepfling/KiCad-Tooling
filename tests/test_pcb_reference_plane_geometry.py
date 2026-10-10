"""Focused geometry PCB reference-plane lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_reference_planes import pcb_reference_plane_entries
from tests.design_lint_fixtures.pcb_reference_planes import (
    RULE,
    ZONE_GND,
    ZONE_OTHER,
    coach,
    mapping,
    report,
    requirement,
    snapshot,
    track,
    zone,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.pcb_reference_lint,
]


class PcbReferencePlaneGeometryTests:
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
        assert control_entry.status == "COMPLETE"
        assert fault_entry.status == "COMPLETE"
        assert (
            control_entry.tracks[0].covered_fraction_numerator,
            control_entry.tracks[0].covered_fraction_denominator,
            control_entry.tracks[0].below_minimum,
        ) == (7, 10, False)
        assert (
            fault_entry.tracks[0].covered_fraction_numerator,
            fault_entry.tracks[0].covered_fraction_denominator,
            fault_entry.tracks[0].below_minimum,
        ) == (3, 5, True)
        assert fault_entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes == (via_id,)

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
        assert control.status == "PASS"
        assert fault.status == "REVIEW"
        assert any(item.rule_id == RULE for item in fault.findings)

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
        assert (
            fault.tracks[0].covered_fraction_numerator,
            fault.tracks[0].covered_fraction_denominator,
        ) == (4, 5)
        assert fault.tracks[0].below_minimum

        exact_hole = (
            (4_000_000, 4_000_000),
            (5_000_000, 4_000_000),
            (5_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        control_source = snapshot(diagonal, zones=(zone(ZONE_GND, holes=(exact_hole,)),))
        control = pcb_reference_plane_entries(mapping(), control_source)[0]
        assert (
            control.tracks[0].covered_fraction_numerator,
            control.tracks[0].covered_fraction_denominator,
        ) == (9, 10)
        assert not control.tracks[0].below_minimum

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
        assert entry.status == "COMPLETE"
        assert (
            entry.tracks[0].covered_fraction_numerator,
            entry.tracks[0].covered_fraction_denominator,
        ) == (1, 1)
        assert entry.tracks[0].reference_zone_uuids == (ZONE_GND, ZONE_OTHER)

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
        assert (
            gnd_entry.tracks[0].covered_fraction_numerator,
            gnd_entry.tracks[0].covered_fraction_denominator,
        ) == (4, 5)
        assert gnd_entry.tracks[0].below_minimum
        review = evaluate(
            "synthetic-split-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=gnd_spec),
            pcb_reference_plane_coverage=report(gnd_spec, split_source),
        )
        assert review.status == "REVIEW"
        assert (
            track().uuid
            in next(item for item in review.findings if item.rule_id == RULE).evidence[
                "below_threshold_track_uuids"
            ]
        )

        agnd_spec = mapping(requirement(reference_net="AGND", minimum_fraction=0.9))
        agnd_source = snapshot(track(), zones=(zone(ZONE_GND, net="AGND"),))
        agnd_entry = pcb_reference_plane_entries(agnd_spec, agnd_source)[0]
        assert (
            agnd_entry.tracks[0].covered_fraction_numerator,
            agnd_entry.tracks[0].covered_fraction_denominator,
        ) == (1, 1)
        control = evaluate(
            "synthetic-split-plane-alternate-domain",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=agnd_spec),
            pcb_reference_plane_coverage=report(agnd_spec, agnd_source),
        )
        assert control.status == "PASS"
        assert not any(item.rule_id == RULE for item in control.findings)

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
        assert [
            (
                item.track_uuid,
                item.covered_fraction_numerator,
                item.covered_fraction_denominator,
                item.below_minimum,
            )
            for item in entry.tracks
        ] == [(trunk.uuid, 1, 1, False), (branch.uuid, 2, 25, True)]

        lint = evaluate(
            "synthetic-branched-route",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        assert lint.status == "REVIEW"
        assert finding.evidence["below_threshold_track_uuids"] == (branch.uuid,)

        reordered = snapshot(branch, trunk, zones=(zone(ZONE_GND, holes=(branch_gap,)),))
        assert pcb_reference_plane_entries(spec, reordered)[0] == entry

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
        assert control.status == "PASS"
        assert not any(item.rule_id == RULE for item in control.findings)

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
        assert entry.status == "COMPLETE"
        assert (
            entry.tracks[0].covered_fraction_numerator,
            entry.tracks[0].covered_fraction_denominator,
        ) == (2, 5)
        assert entry.tracks[0].endpoint_via_ids == (via_id,)
        assert entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes == (via_id,)
        lint = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        assert lint.status == "REVIEW"
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        assert "do not identify which clearance created a hole" in finding.message
        assert finding.evidence["endpoint_via_hole_candidates"] == (via_id,)

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
        assert "may be expected antipads" not in unrelated_finding.message
        assert unrelated_finding.evidence["endpoint_via_hole_candidates"] == ()

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
        assert (
            unrelated_hole.tracks[0].covered_fraction_numerator
            == entry.tracks[0].covered_fraction_numerator
        )
        assert unrelated_hole.tracks[0].endpoint_via_ids == (via_id,)
        assert unrelated_hole.tracks[0].endpoint_via_ids_with_center_in_reference_holes == ()
