"""Cross-process determinism for MOSFET drain/source same-net review."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.slow]

RULE_ID = "component.mosfet_drain_source_same_net"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mosfet_same_net_fault_and_distinct_net_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["mosfet_drain_source_same_net_fault"]
    control = reports["mosfet_drain_source_same_net_control"]
    fault_findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]

    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["drain_net"] == ["SWITCHED"]
    assert fault_findings[0]["evidence"]["source_net"] == ["SWITCHED"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != RULE_ID for item in control["findings"])
