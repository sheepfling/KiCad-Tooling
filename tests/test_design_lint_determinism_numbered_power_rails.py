"""Cross-process determinism for numbered negative supply rail reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

RULE_ID = "net.numbered_power_rails"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _finding_rule_ids(report: JsonObject) -> set[str]:
    return {str(finding["rule_id"]) for finding in report["findings"]}


def test_numbered_negative_power_rail_fault_and_control_are_hashseed_stable() -> None:
    reports = hashseed_probe_reports(families=("numbered_power_rails",))
    fault = reports["numbered_negative_power_rail_fault"]
    control = reports["numbered_negative_power_rail_control"]

    assert fault != control
    assert RULE_ID in _finding_rule_ids(fault)
    assert RULE_ID not in _finding_rule_ids(control)
