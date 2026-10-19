"""Hash-seed regressions for project-mapped touch-pad clearance reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_touch_pad_clearance_fault_and_boundary_reports_are_source_bound_and_deterministic() -> (
    None
):
    reports = hashseed_probe_reports(families=("pcb_touch_pad_clearance",))
    fault_case = reports["pcb_touch_pad_clearance_fault"]
    control_case = reports["pcb_touch_pad_clearance_boundary_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["board_sha256"] != control_case["board_sha256"]
    assert fault_case["snapshot_sha256"] != control_case["snapshot_sha256"]
    assert fault_case["netlist_sha256"] == control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    assert fault["pcb_touch_pad_clearance_coverage"]["status"] == "COMPLETE"
    (fault_entry,) = fault["pcb_touch_pad_clearance_coverage"]["entries"]
    assert fault_entry["status"] == "COMPLETE"
    assert fault_entry["minimum_clearance_nm"] == 800_000
    assert fault_entry["measured_clearance_nm"] == 500_000
    assert [item["rule_id"] for item in fault["findings"]] == ["pcb.touch_pad_reference_clearance"]
    fault_evidence = fault["findings"][0]["evidence"]
    assert fault_evidence["minimum_clearance_nm"] == ["800000"]
    assert fault_evidence["measured_clearance_nm"] == ["500000"]
    assert fault_evidence["violates_minimum_clearance"] == ["true"]
    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    assert control["pcb_touch_pad_clearance_coverage"]["status"] == "COMPLETE"
    (control_entry,) = control["pcb_touch_pad_clearance_coverage"]["entries"]
    assert control_entry["status"] == "COMPLETE"
    assert control_entry["minimum_clearance_nm"] == 800_000
    assert control_entry["measured_clearance_nm"] == 800_000
    assert control["findings"] == []
