"""Hash-seed regressions for mapped PCB differential-pair DRC coverage."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_differential_pair_drc_coverage_reports_remain_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_drc",))
    fault_case = reports["pcb_differential_pair_rule_fault"]
    control_case = reports["pcb_differential_pair_rule_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["rules_sha256"] != control_case["rules_sha256"]
    assert fault_case["source_inventory_sha256"] != control_case["source_inventory_sha256"]
    assert fault_case["project_sha256"] == control_case["project_sha256"]
    assert fault_case["board_sha256"] == control_case["board_sha256"]
    assert fault_case["netlist_sha256"] == control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["pcb_differential_pair_rules"]["status"] == "INCOMPLETE"
    assert fault["pcb_differential_pair_rules"]["rules_sha256"] == fault_case["rules_sha256"]
    assert any(
        item["status"] == "MISMATCH"
        for item in fault["pcb_differential_pair_rules"]["entries"][0]["constraints"]
    )
    assert "pcb.differential_pair_rule_coverage" in {item["rule_id"] for item in fault["findings"]}

    assert control["status"] == "PASS"
    assert control["pcb_differential_pair_rules"]["status"] == "COMPLETE"
    assert control["pcb_differential_pair_rules"]["rules_sha256"] == control_case["rules_sha256"]
    assert control["findings"] == []
