"""Cross-process hash-seed coverage for SWD same-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.swdio_swclk_same_net"
CONNECTOR_RULE_ID = "bus.swd_generic_connector_pair_review"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.design_lint_rule(rule_id=CONNECTOR_RULE_ID),
]


def test_swd_fault_and_control_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("swd_signal_same_net",))
    fault = reports["swd_signal_same_net_fault"]
    control = reports["swd_signal_same_net_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert fault["status"] == "REVIEW"
    assert len(findings) == 1
    assert findings[0]["subject"] == "U1: SWDIO U1.5 and SWCLK U1.6 share SWD_SHARED"
    assert findings[0]["evidence"]["SWDIO_pin"] == ["U1.5"]
    assert findings[0]["evidence"]["SWCLK_pin"] == ["U1.6"]
    assert findings[0]["evidence"]["shared_net"] == ["SWD_SHARED"]
    assert control["status"] == "REVIEW"
    assert any(item["rule_id"] == CONNECTOR_RULE_ID for item in control["findings"])
    assert all(item["rule_id"] != RULE_ID for item in control["findings"])
    assert fault["netlist_sha256"] != control["netlist_sha256"]
