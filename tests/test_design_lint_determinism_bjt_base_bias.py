"""Cross-process determinism checks for the BJT base-bias heuristic."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.slow]

RULE_ID = "component.bjt_base_without_visible_emitter_bias"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bjt_base_bias_fault_and_resistor_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["bjt_base_bias_fault"]
    control = reports["bjt_base_bias_resistor_control"]

    fault_findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["base_net"] == ["BASE"]
    assert fault_findings[0]["evidence"]["emitter_net"] == ["EMITTER"]
    assert control["status"] == "PASS"
    assert control["findings"] == []
