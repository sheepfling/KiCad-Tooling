"""Cross-process determinism for the mapped-other contact review rule."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "connector.mapped_interface_other_unassigned"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_other_contact_fault_and_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("mapped_interface_other_unassigned",))
    fault_case = reports["mapped_interface_other_fault"]
    control_case = reports["mapped_interface_other_control"]

    assert fault_case["interface_catalog_sha256"] == control_case["interface_catalog_sha256"]
    assert fault_case["coverage_sha256"] != control_case["coverage_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    fault_findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]
    control_findings = [item for item in control["findings"] if item["rule_id"] == RULE_ID]
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["component_pin"] == ["J1.2"]
    assert control_findings == []
