"""Hash-seed regressions for mapped PCB protection-path reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


def test_mapped_protection_path_reports_remain_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_measurements",))
    fault_case = reports["pcb_protection_path_fault"]
    control_case = reports["pcb_protection_path_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["board_sha256"] != control_case["board_sha256"]
    assert fault_case["snapshot_sha256"] != control_case["snapshot_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    assert fault["pcb_protection_path"]["status"] == "INCOMPLETE"
    assert "pcb.protection_entry_path" in {item["rule_id"] for item in fault["findings"]}

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    assert control["pcb_protection_path"]["status"] == "COMPLETE"
    assert control["findings"] == []
