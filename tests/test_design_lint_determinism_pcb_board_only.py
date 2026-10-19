"""Hash-seed regressions for opt-in board-only footprint review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_board_only_candidate_and_matched_control_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_board_only_footprints",))
    candidate_case = reports["pcb_board_only_mounting_hole_candidate"]
    control_case = reports["pcb_board_only_matched_inventory_control"]

    assert candidate_case["board_sha256"] != control_case["board_sha256"]
    assert candidate_case["snapshot_sha256"] != control_case["snapshot_sha256"]
    assert candidate_case["netlist_sha256"] == control_case["netlist_sha256"]

    candidate = candidate_case["report"]
    control = control_case["report"]
    assert candidate["status"] == "REVIEW"
    assert candidate["netlist_sha256"] == candidate_case["netlist_sha256"]
    candidate_inventory = candidate["pcb_component_inventory"]
    assert candidate_inventory["board_sha256"] == candidate_case["board_sha256"]
    assert candidate_inventory["snapshot_sha256"] == candidate_case["snapshot_sha256"]
    candidate_coverage = candidate_inventory["board_only_footprint_coverage"]
    assert candidate_coverage["status"] == "COMPLETE"
    assert candidate_coverage["mode"] == "review"
    assert [item["reference"] for item in candidate_coverage["footprints"]] == ["H_MOUNT1"]
    assert [item["rule_id"] for item in candidate["findings"]] == ["pcb.board_only_footprint"]
    assert candidate["findings"][0]["mode"] == "review"
    assert candidate["findings"][0]["disposition"] == "OPEN"

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    control_coverage = control["pcb_component_inventory"]["board_only_footprint_coverage"]
    assert control_coverage["status"] == "COMPLETE"
    assert control_coverage["mode"] == "review"
    assert control_coverage["footprints"] == []
    assert control["findings"] == []
