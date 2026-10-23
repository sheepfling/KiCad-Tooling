"""Cross-process determinism for the mapped-other named-rail review rule."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "connector.mapped_interface_other_named_rail"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_other_named_rail_fault_and_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("mapped_interface_other_named_rail",))
    fault_case = reports["mapped_other_named_rail_fault"]
    control_case = reports["mapped_other_named_rail_control"]

    assert fault_case["interface_catalog_sha256"] == control_case["interface_catalog_sha256"]
    assert fault_case["coverage_sha256"] != control_case["coverage_sha256"]
    fault_findings = [
        item for item in fault_case["report"]["findings"] if item["rule_id"] == RULE_ID
    ]
    control_findings = [
        item for item in control_case["report"]["findings"] if item["rule_id"] == RULE_ID
    ]
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["component_pin"] == ["J1.2"]
    assert fault_findings[0]["evidence"]["assigned_nets"] == ["GND"]
    assert control_findings == []
