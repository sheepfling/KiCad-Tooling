"""Cross-process determinism for asymmetric USB-C SBU reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.usb_c_sbu_unconnected_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_usb_c_sbu_unconnected_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_sbu_unconnected_pin",))
    fault = reports["usb_c_sbu_unconnected_pin_fault"]
    control = reports["usb_c_sbu_unconnected_pin_control"]

    assert fault["status"] == "REVIEW"
    assert sum(item["rule_id"] == RULE_ID for item in fault["findings"]) == 1
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])


@pytest.mark.design_lint_rule(rule_id="bus.usb_c_sbu_same_net")
def test_usb_c_sbu_same_net_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("usb_c_sbu_same_net",))
    fault = reports["usb_c_sbu_same_net_fault"]
    control = reports["usb_c_sbu_same_net_control"]

    assert fault["status"] == "REVIEW"
    assert sum(item["rule_id"] == "bus.usb_c_sbu_same_net" for item in fault["findings"]) == 1
    assert not any(item["rule_id"] == "bus.usb_c_sbu_same_net" for item in control["findings"])
