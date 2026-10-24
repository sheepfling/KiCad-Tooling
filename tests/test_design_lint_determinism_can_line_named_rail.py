"""Cross-process determinism for CANH/CANL named-rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.can_line_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_can_line_named_rail_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("can_line_named_rail",))
    fault = reports["can_line_named_rail_fault"]
    control = reports["can_line_named_rail_control"]

    assert fault["status"] == "REVIEW"
    line_findings = tuple(item for item in fault["findings"] if item["rule_id"] == RULE_ID)
    assert len(line_findings) == 2
    assert not any(item["rule_id"] == RULE_ID for item in control["findings"])
