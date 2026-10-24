"""Cross-process hash-seed coverage for USB-C CC1/CC2 same-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.usb_c_cc_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_usb_c_cc_same_net_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_cc_same_net",))
    fault = reports["usb_c_cc_same_net_fault"]
    control = reports["usb_c_cc_same_net_control"]
    fault_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in fault_findings) == (
        "J1: USB-C CC1/CC2 pins share CC_SHARED",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
