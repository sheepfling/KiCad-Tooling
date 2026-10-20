"""Cross-process determinism for split peers with missing pin metadata."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
]

RULE_ID = "connector.footprint_peer_pin_missing_metadata_assignment_divergence"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_peer_fault_and_control_are_hashseed_stable() -> None:
    reports = hashseed_probe_reports(families=("connector_peer_missing_metadata",))
    fault = reports["connector_peer_missing_metadata_fault"]
    control = reports["connector_peer_missing_metadata_control"]

    assert isinstance(fault, dict)
    assert isinstance(control, dict)
    assert fault.get("status") == "REVIEW"
    assert control.get("status") != "REVIEW"

    fault_findings = fault.get("findings")
    control_findings = control.get("findings")
    assert isinstance(fault_findings, list)
    assert isinstance(control_findings, list)
    assert any(isinstance(item, dict) and item.get("rule_id") == RULE_ID for item in fault_findings)
    assert not any(
        isinstance(item, dict) and item.get("rule_id") == RULE_ID for item in control_findings
    )
