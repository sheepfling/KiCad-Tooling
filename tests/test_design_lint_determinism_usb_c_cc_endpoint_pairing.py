"""Cross-process determinism for USB-C CC endpoint-pairing review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.usb_c_cc_endpoint_crossed"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_crossed_usb_c_cc_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_cc_endpoint_pairing",))
    fault = reports["usb_c_cc_endpoint_pairing_fault"]
    control = reports["usb_c_cc_endpoint_pairing_control"]
    findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in findings) == (
        "J1/U1: USB-C CC1/CC2 endpoint nets appear crossed",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
