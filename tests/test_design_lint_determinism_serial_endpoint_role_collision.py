"""Cross-process determinism for UART endpoint-role collision review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.serial_endpoint_role_collision"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_serial_endpoint_role_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("serial_endpoint_role_collision",))
    fault = reports["serial_endpoint_role_collision_fault"]
    control = reports["serial_endpoint_role_collision_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in findings) == (
        "J1/U1: serial RX functions share UART_RX",
        "J1/U1: serial TX functions share UART_TX",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
