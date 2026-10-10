"""Focused layers PCB reference-plane lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
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


class PcbReferencePlaneLayerTests:
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
        assert (
            entry.tracks[0].covered_fraction_numerator,
            entry.tracks[0].covered_fraction_denominator,
        ) == (1, 5)
        assert entry.tracks[0].endpoint_via_ids_with_center_in_reference_holes == (endpoint_via_id,)

        lint = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, source),
        )
        finding = next(item for item in lint.findings if item.rule_id == RULE)
        assert "do not identify which clearance created a hole" in finding.message
        assert "inspect the geometry" in finding.message
        assert finding.evidence["endpoint_via_hole_candidates"] == (endpoint_via_id,)

    def test_only_immediately_adjacent_exact_reference_net_copper_counts(self) -> None:
        source = snapshot(
            track(),
            zones=(
                zone(ZONE_OTHER, layer="In1.Cu", net="SHIELD"),
                zone(ZONE_GND, layer="B.Cu"),
            ),
        )
        entry = pcb_reference_plane_entries(mapping(), source)[0]
        assert entry.status == "COMPLETE"
        assert len(entry.tracks) == 1
        assert entry.tracks[0].reference_layer == "In1.Cu"
        assert entry.tracks[0].reference_zone_uuids == ()
        assert entry.tracks[0].covered_fraction_numerator == 0
        assert entry.tracks[0].below_minimum

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
        assert [
            (
                item.reference_layer,
                item.covered_fraction_numerator,
                item.covered_fraction_denominator,
                item.below_minimum,
            )
            for item in entry.tracks
        ] == [("F.Cu", 4, 5, True), ("B.Cu", 0, 1, True)]

        full_source = snapshot(
            track(layer="In1.Cu"),
            zones=(zone(ZONE_GND, layer="F.Cu"),),
        )
        full_entry = pcb_reference_plane_entries(mapping(requirement(layer="In1.Cu")), full_source)[
            0
        ]
        assert not all(item.below_minimum for item in full_entry.tracks)
        spec = mapping(requirement(layer="In1.Cu"))
        control = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, full_source),
        )
        assert control.status == "PASS"
        assert not any(item.rule_id == RULE for item in control.findings)

    def test_short_segments_are_excluded_and_arcs_keep_coverage_incomplete(self) -> None:
        short = track("1", start=(0, 0), end=(999_999, 0))
        short_entry = pcb_reference_plane_entries(
            mapping(requirement(minimum_length_um=1000)), snapshot(short)
        )[0]
        assert short_entry.status == "INCOMPLETE"
        assert short_entry.excluded_short_track_uuids == (short.uuid,)
        assert "minimum segment length" in short_entry.issues[0]

        arc_entry = pcb_reference_plane_entries(mapping(), snapshot(track(geometry="arc")))[0]
        assert arc_entry.status == "INCOMPLETE"
        assert "unsupported arc geometry" in arc_entry.issues[0]
        assert arc_entry.tracks == ()

    def test_excluded_short_track_review_is_opt_in_and_cli_text_keeps_ids_visible(self) -> None:
        long_track = track("2", start=(0, 0), end=(5_000_000, 0))
        short_track = track("3", start=(0, 1_000_000), end=(999_999, 1_000_000))
        source = snapshot(long_track, short_track)

        quiet_spec = mapping(requirement(minimum_length_um=1000))
        quiet_entry = pcb_reference_plane_entries(quiet_spec, source)[0]
        assert quiet_entry.status == "COMPLETE"
        assert quiet_entry.excluded_short_track_uuids == (short_track.uuid,)
        quiet = evaluate(
            "synthetic-short-track-policy",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=quiet_spec),
            pcb_reference_plane_coverage=report(quiet_spec, source),
        )
        assert quiet.status == "PASS"
        assert not any(item.rule_id == RULE for item in quiet.findings)
        quiet_text = text_report(quiet)
        assert "short-track review disabled" in quiet_text
        assert short_track.uuid in quiet_text

        review_spec = mapping(
            requirement(minimum_length_um=1000, review_excluded_short_tracks=True)
        )
        review_entry = pcb_reference_plane_entries(review_spec, source)[0]
        assert review_entry.status == "INCOMPLETE"
        assert "require review" in review_entry.issues[0]
        reviewed = evaluate(
            "synthetic-short-track-policy",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=review_spec),
            pcb_reference_plane_coverage=report(review_spec, source),
        )
        assert reviewed.status == "REVIEW"
        finding = next(item for item in reviewed.findings if item.rule_id == RULE)
        assert finding.evidence["excluded_short_track_uuids"] == (short_track.uuid,)
        assert finding.evidence["review_excluded_short_tracks"] == ("true",)
        assert "were excluded" in finding.message
        assert "short-track review enabled" in text_report(reviewed)

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
        assert blocking.status == "FAIL"

        reordered = snapshot(short_track, long_track)
        assert pcb_reference_plane_entries(quiet_spec, reordered)[0] == quiet_entry

    def test_unmapped_track_and_missing_stack_layer_remain_incomplete(self) -> None:
        no_tracks = pcb_reference_plane_entries(mapping(), snapshot())[0]
        assert no_tracks.status == "INCOMPLETE"
        assert "No native track items" in no_tracks.issues[0]

        missing_layer = snapshot(track(), copper_layers=("In1.Cu", "B.Cu"))
        incomplete = pcb_reference_plane_entries(mapping(), missing_layer)[0]
        assert incomplete.status == "INCOMPLETE"
        assert "Mapped signal layer F.Cu is absent" in incomplete.issues[0]
        assert any("no observed adjacent copper layer" in item for item in incomplete.issues)
