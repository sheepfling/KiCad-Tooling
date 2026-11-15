"""Cross-process determinism for USB-C SBU named-rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.usb_c_sbu_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_usb_c_sbu_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_sbu_named_rail",))
    fault = reports["usb_c_sbu_named_rail_fault"]
    control = reports["usb_c_sbu_named_rail_control"]
    connector_fault = reports["usb_c_sbu_named_rail_connector_fault"]
    connector_control = reports["usb_c_sbu_named_rail_connector_control"]
    connector_findings = tuple(
        item for item in connector_fault["findings"] if item["rule_id"] == RULE_ID
    )

    assert fault["status"] == "REVIEW"
    assert len(tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)) == 2
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
    assert tuple(item["subject"] for item in connector_findings) == (
        "J1.1: SBU1 on return-like net GND",
        "J1.2: SBU2 on supply-like net +3V3",
    )
    assert not any(item["rule_id"] == RULE_ID for item in connector_control["findings"])
