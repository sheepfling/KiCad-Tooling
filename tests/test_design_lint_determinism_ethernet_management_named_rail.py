"""Process-level determinism for Ethernet management named-rail review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.ethernet_management_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_ethernet_management_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("ethernet_management_named_rail",))
    fault = reports["ethernet_management_named_rail_fault"]
    control = reports["ethernet_management_named_rail_control"]
    connector_fault = reports["ethernet_management_named_rail_connector_fault"]
    connector_control = reports["ethernet_management_named_rail_connector_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)
    connector_findings = tuple(
        item for item in connector_fault["findings"] if item["rule_id"] == RULE_ID
    )

    assert tuple(item["subject"] for item in findings) == ("U1.5: MDC on return-like net GND",)
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
    assert tuple(item["subject"] for item in connector_findings) == (
        "J1.1: MDC on return-like net GND",
        "J1.2: MDIO on supply-like net +3V3",
    )
    assert not any(item["rule_id"] == RULE_ID for item in connector_control["findings"])
