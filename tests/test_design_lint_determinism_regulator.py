"""Hash-seed regressions for mapped regulator-feedback reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.power_lint]


def test_mapped_regulator_feedback_reports_remain_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("analog",))
    fault_case = reports["mapped_regulator_feedback_fault"]
    control_case = reports["mapped_regulator_feedback_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["netlist_sha256"] != control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    assert fault["regulator_feedback_coverage"]["status"] == "COMPLETE"
    assert fault["regulator_feedback_coverage"]["entries"][0]["status"] == "OUT_OF_RANGE"
    assert "power.regulator_feedback_mismatch" in {
        finding["rule_id"] for finding in fault["findings"]
    }

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    assert control["regulator_feedback_coverage"]["status"] == "COMPLETE"
    assert control["regulator_feedback_coverage"]["entries"][0]["status"] == "COMPLETE"
    assert control["findings"] == []
