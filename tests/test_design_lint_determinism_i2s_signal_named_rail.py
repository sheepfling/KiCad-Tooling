"""Cross-process hash-seed coverage for I2S named-rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.i2s_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_i2s_signal_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("i2s_signal_named_rail",))
    fault = reports["i2s_signal_named_rail_fault"]
    control = reports["i2s_signal_named_rail_control"]
    connector_fault = reports["i2s_signal_named_rail_connector_fault"]
    connector_control = reports["i2s_signal_named_rail_connector_control"]
    fault_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)
    connector_findings = tuple(
        item for item in connector_fault["findings"] if item["rule_id"] == RULE_ID
    )

    assert tuple(item["subject"] for item in fault_findings) == (
        "U1.1: I2S_BCLK on return-like net GND",
        "U1.3: I2S_DATA on supply-like net +3V3",
    )
    assert tuple(item["subject"] for item in connector_findings) == (
        "J1.1: BCLK on return-like net GND",
        "J1.3: SDOUT on supply-like net +3V3",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
    assert not any(item["rule_id"] == RULE_ID for item in connector_control["findings"])
