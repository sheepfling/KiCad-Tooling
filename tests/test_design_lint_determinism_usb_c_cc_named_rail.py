"""Cross-process determinism for USB-C CC named-rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.usb_c_cc_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_usb_c_cc_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_cc_named_rail",))
    fault = reports["usb_c_cc_named_rail_fault"]
    control = reports["usb_c_cc_named_rail_control"]

    assert fault["status"] == "REVIEW"
    assert len(tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)) == 2
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
