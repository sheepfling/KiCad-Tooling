"""Hash-seed determinism for source-bound PCB UUID findings."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "pcb.duplicate_object_uuid"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_uuid_fault_and_control_reports_are_deterministic_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("pcb_uuid_integrity",))
    fault = reports["pcb_uuid_duplicate_fault"]
    control = reports["pcb_uuid_duplicate_control"]
    findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]

    assert fault["status"] == "REVIEW"
    assert len(findings) == 1
    assert findings[0]["evidence"]["object_uuid"] == ["00000000-0000-0000-0000-000000000002"]
    assert findings[0]["evidence"]["occurrence_object_kinds"] == ["segment", "segment"]
    assert not [item for item in control["findings"] if item["rule_id"] == RULE_ID]
