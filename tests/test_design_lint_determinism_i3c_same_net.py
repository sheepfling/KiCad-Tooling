"""Cross-process hash-seed coverage for I3C same-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.i3c_sda_scl_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_i3c_same_net_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("i3c_same_net",))
    fault = reports["i3c_same_net_fault"]
    control = reports["i3c_same_net_control"]
    fault_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in fault_findings) == (
        "U1: I3C1 SDA/SCL pins share I3C_SHARED",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
