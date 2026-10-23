"""Process-level determinism for mapped shields on named supply rails."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "connector.mapped_interface_shield_on_supply_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shield_supply_rail_fault_and_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("mapped_interface_shield_supply_rail",))
    fault = reports["mapped_shield_supply_rail_fault"]["report"]
    control = reports["mapped_shield_supply_rail_control"]["report"]

    fault_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)
    control_findings = tuple(item for item in control["findings"] if item["rule_id"] == RULE_ID)
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["component_pin"] == ["J1.2"]
    assert not control_findings
