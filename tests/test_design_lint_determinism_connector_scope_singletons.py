"""Hash-seed regression for mapped connector return-scope coverage."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "connector.return_supply_scope_singleton"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_return_scope_singleton_fault_and_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("connector_scope_singletons",))
    fault_case = reports["connector_return_scope_singleton_fault"]
    control_case = reports["connector_return_scope_singleton_control"]

    assert fault_case["netlist_sha256"] == control_case["netlist_sha256"]
    assert fault_case["interface_catalog_sha256"] == control_case["interface_catalog_sha256"]
    assert fault_case["coverage_sha256"] != control_case["coverage_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    fault_findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]
    control_findings = [item for item in control["findings"] if item["rule_id"] == RULE_ID]
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["isolated_references"] == ["J2"]
    assert control_findings == []
