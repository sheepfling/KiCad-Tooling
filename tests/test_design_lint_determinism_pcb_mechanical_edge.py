"""Hash-seed regressions for courtyard-to-edge DRC rule coverage."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "pcb.mechanical_edge_clearance_rule_coverage"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_mechanical_edge_fault_and_control_reports_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_mechanical_edge_clearance",))
    fault_case = reports["pcb_mechanical_edge_coverage_fault"]
    control_case = reports["pcb_mechanical_edge_coverage_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["project_sha256"] == control_case["project_sha256"]
    assert fault_case["board_sha256"] == control_case["board_sha256"]
    assert fault_case["source_inventory_sha256"] != control_case["source_inventory_sha256"]
    assert fault_case["rules_sha256"] != control_case["rules_sha256"]
    assert fault_case["native_summary_sha256"] == control_case["native_summary_sha256"]
    assert fault_case["native_drc_sha256"] == control_case["native_drc_sha256"]
    assert fault_case["netlist_sha256"] == control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert (
        fault["source_hashes"]["projects/synthetic-mechanical-edge-clearance/board.kicad_dru"]
        == (fault_case["rules_sha256"])
    )
    assert {
        path
        for path, digest in fault["source_hashes"].items()
        if digest != control["source_hashes"].get(path)
    } == {"projects/synthetic-mechanical-edge-clearance/board.kicad_dru"}
    (finding,) = fault["findings"]
    assert finding["rule_id"] == RULE_ID
    assert finding["evidence"]["expected_minimum_clearance_nm"] == ["1500000"]
    assert finding["evidence"]["observed_constraint_bounds"] == [
        "physical_clearance:min=1000000;max=None"
    ]

    assert control["status"] == "PASS"
    assert (
        control["source_hashes"]["projects/synthetic-mechanical-edge-clearance/board.kicad_dru"]
        == (control_case["rules_sha256"])
    )
    assert control["findings"] == []
