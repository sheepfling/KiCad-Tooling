"""Cross-process hash-seed coverage for SWD named-rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.swd_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_swd_signal_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("swd_signal_named_rail",))
    fault = reports["swd_signal_named_rail_fault"]
    control = reports["swd_signal_named_rail_control"]
    fault_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)

    assert tuple(item["subject"] for item in fault_findings) == (
        "U1.1: SYS_JTMS-SWDIO on return-like net GND",
        "U1.2: SYS_JTCK-SWCLK on supply-like net +3V3",
        "U1.3: SWO on supply-like net +1V8",
    )
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
