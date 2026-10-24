"""Cross-process hash-seed coverage for RS-485 A/B same-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.rs485_ab_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_rs485_ab_same_net_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("rs485_ab_same_net",))
    fault = reports["rs485_ab_same_net_fault"]
    control = reports["rs485_ab_same_net_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in findings) == (
        "U1: RS-485 A/B bus pins share AB_SHARED",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
