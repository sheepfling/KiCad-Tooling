"""Cross-process hash-seed coverage for I2S clock/data same-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.i2s_clock_data_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_i2s_clock_data_fault_and_control_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("i2s_clock_data_same_net",))
    fault = reports["i2s_clock_data_same_net_fault"]
    control = reports["i2s_clock_data_same_net_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert fault["status"] == "REVIEW"
    assert len(findings) == 1
    assert findings[0]["subject"] == (
        "U1: I2S bit clock U1.1 and serial data U1.3 share I2S_SHARED"
    )
    assert findings[0]["evidence"]["shared_net"] == ["I2S_SHARED"]
    assert findings[0]["evidence"]["bit_clock_pin"] == ["U1.1"]
    assert findings[0]["evidence"]["data_pin"] == ["U1.3"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != RULE_ID for item in control["findings"])
    assert fault["netlist_sha256"] != control["netlist_sha256"]
