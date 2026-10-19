"""Hash-seed regressions for explicit PCB fitted-reference requirements."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_required_fitted_reference_reports_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_required_fitted_reference",))
    fault_case = reports["pcb_required_fitted_reference_dnp_fault"]
    control_case = reports["pcb_required_fitted_reference_fitted_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["board_sha256"] != control_case["board_sha256"]
    assert fault_case["snapshot_sha256"] != control_case["snapshot_sha256"]
    assert fault_case["netlist_sha256"] != control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "FAIL"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    fault_inventory = fault["pcb_component_inventory"]
    assert fault_inventory["board_sha256"] == fault_case["board_sha256"]
    assert fault_inventory["snapshot_sha256"] == fault_case["snapshot_sha256"]
    fault_coverage = fault_inventory["required_fitted_reference_coverage"]
    assert fault_coverage["status"] == "COMPLETE"
    assert fault_coverage["map_sha256"] == fault_case["requirement_sha256"]
    assert fault_coverage["mismatches"][0]["violations"] == [
        "schematic_component_dnp",
        "board_footprint_dnp",
    ]
    assert [item["rule_id"] for item in fault["findings"]] == ["pcb.required_fitted_reference"]
    assert fault["findings"][0]["mode"] == "block"
    assert fault["findings"][0]["disposition"] == "OPEN"

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    control_inventory = control["pcb_component_inventory"]
    assert control_inventory["board_sha256"] == control_case["board_sha256"]
    assert control_inventory["snapshot_sha256"] == control_case["snapshot_sha256"]
    control_coverage = control_inventory["required_fitted_reference_coverage"]
    assert control_coverage["status"] == "COMPLETE"
    assert control_coverage["map_sha256"] == control_case["requirement_sha256"]
    assert control_coverage["mismatches"] == []
    assert control["findings"] == []
