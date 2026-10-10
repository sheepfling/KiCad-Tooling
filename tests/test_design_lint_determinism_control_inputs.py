"""Cross-process hash-seed checks for control-input lint reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.power_lint,
]


def test_control_input_fault_and_valid_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("control_inputs",))
    assert set(reports) == {
        "control_input_unconnected_fault",
        "control_input_connected_control",
    }
    fault = reports["control_input_unconnected_fault"]
    control = reports["control_input_connected_control"]

    assert fault["netlist_sha256"] != control["netlist_sha256"]
    assert fault["status"] == "REVIEW"
    findings = [
        item for item in fault["findings"] if item["rule_id"] == "control.unconnected_control_input"
    ]
    assert len(findings) == 9
    assert [item["subject"] for item in findings] == sorted(item["subject"] for item in findings)
    assert control["status"] == "PASS"
    assert control["findings"] == []
