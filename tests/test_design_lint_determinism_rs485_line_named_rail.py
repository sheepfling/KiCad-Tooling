"""Process-level determinism for RS-485 A/B named-rail review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.rs485_line_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_rs485_line_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("rs485_line_named_rail",))
    fault = reports["rs485_line_named_rail_fault"]
    control = reports["rs485_line_named_rail_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in findings) == ("U1.1: A on return-like net GND",)
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
