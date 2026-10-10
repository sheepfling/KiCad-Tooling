from __future__ import annotations

import unittest

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    PcbSwitchingLoopCoverageEntry,
    PcbSwitchingLoopRequirement,
)
from kicad_tooling.hwrepo.pcb_switching_loops import pcb_switching_loop_entries
from tests.design_lint_fixtures.pcb_switching_loop import (
    PLANE_UUID,
    coach,
    contoured_snapshot,
    coverage,
    design_lint_report,
    long_routed_snapshot,
    routed_mapping,
    routed_snapshot,
    via_routed_snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]

RULE = "pcb.switching_loop_geometry"


class PcbSwitchingLoopRouteTests(unittest.TestCase):
    def test_detour_changes_trace_measurement_while_pad_center_proxy_stays_fixed(self) -> None:
        straight = pcb_switching_loop_entries(routed_mapping(), routed_snapshot())[0]
        detoured = pcb_switching_loop_entries(routed_mapping(), routed_snapshot(detour=True))[0]

        self.assertEqual(detoured.loop_area_twice_nm2, straight.loop_area_twice_nm2)
        self.assertNotEqual(
            detoured.route_edges[0].vertices_nm, straight.route_edges[0].vertices_nm
        )
        self.assertGreater(detoured.route_edges[0].length_nm, straight.route_edges[0].length_nm)

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

    def test_long_trace_chain_resolves_without_recursive_search(self) -> None:
        result = pcb_switching_loop_entries(routed_mapping(), long_routed_snapshot(1_100))[0]

        self.assertEqual(result.route_edges[0].status, "RESOLVED")
        self.assertEqual(len(result.route_edges[0].track_uuids), 1_100)
        self.assertEqual(result.route_edges[0].vertices_nm[0], (0, 0))
        self.assertEqual(result.route_edges[0].vertices_nm[-1], (1_000_000, 0))
        self.assertEqual(result.route_edges[0].length_nm, 1_000_000)

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

    def test_schema_nine_plane_edge_reports_exact_filled_contour_area(self) -> None:
        result = pcb_switching_loop_entries(routed_mapping(), contoured_snapshot())[0]
        plane_edge = result.route_edges[2]

        self.assertEqual(plane_edge.status, "DECLARED")
        self.assertEqual(plane_edge.plane_zone_uuid, PLANE_UUID)
        self.assertEqual(plane_edge.plane_island_index, 0)
        self.assertEqual(plane_edge.plane_island_area_twice_nm2, 22_000_000_000_000)
        self.assertIn("filled-island contour area is recorded", plane_edge.issue)

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


def test_design_lint_reports_ambiguous_trace_chain_incomplete() -> None:
    report = design_lint_report(ambiguous_route=True)
    entry = report.pcb_switching_loop.entries[0]
    trace = entry.route_edges[0]

    assert report.status == "REVIEW"
    assert entry.route_status == "INCOMPLETE"
    assert trace.status == "INCOMPLETE"
    assert trace.issue == "More than one native track chain connects the mapped pads"
    assert {finding.rule_id for finding in report.findings} == {RULE}


def test_design_lint_keeps_unmeasured_edge_review_after_unique_trace() -> None:
    report = design_lint_report(ambiguous_route=False)
    entry = report.pcb_switching_loop.entries[0]
    trace = entry.route_edges[0]

    assert report.status == "REVIEW"
    assert trace.status == "RESOLVED"
    assert trace.length_nm == 1_000_000
    assert any("component geometry is not measured" in issue for issue in entry.issues)
    assert {finding.rule_id for finding in report.findings} == {RULE}
