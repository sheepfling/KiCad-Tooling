"""Hash-seed determinism for hierarchical schematic UUID findings."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "schematic.duplicate_object_uuid"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_uuid_reports_are_deterministic_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("schematic_uuid_integrity",))
    fault = reports["schematic_uuid_cross_file_fault"]
    control = reports["schematic_uuid_cross_file_control"]

    findings = [item for item in fault["findings"] if item["rule_id"] == RULE_ID]
    assert fault["status"] == "REVIEW"
    assert len(findings) == 1
    assert findings[0]["evidence"]["object_uuid"] == ["b0000000-0000-4000-8000-000000000005"]
    assert findings[0]["evidence"]["occurrence_source_paths"] == [
        "projects/synthetic/kicad/channel-a.kicad_sch",
        "projects/synthetic/kicad/channel-b.kicad_sch",
    ]
    assert not [item for item in control["findings"] if item["rule_id"] == RULE_ID]
