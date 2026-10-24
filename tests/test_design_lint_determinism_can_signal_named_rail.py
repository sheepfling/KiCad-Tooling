"""Process-level determinism for CAN named-rail review findings."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.can_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_can_signal_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("can_signal_named_rail",))
    fault = reports["can_signal_named_rail_fault"]
    control = reports["can_signal_named_rail_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in findings) == ("U1.1: CAN1_TX on return-like net GND",)
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
