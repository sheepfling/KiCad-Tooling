"""Cross-process determinism for split peers with missing pin metadata."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from pydantic import JsonValue

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
]

RULE_ID = "connector.footprint_peer_pin_missing_metadata_assignment_divergence"


def _matching_rule_findings(findings: Sequence[JsonValue]) -> list[dict[str, JsonValue]]:
    matches: list[dict[str, JsonValue]] = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        finding: dict[str, JsonValue] = item
        if finding.get("rule_id") == RULE_ID:
            matches.append(finding)
    return matches


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_peer_fault_and_control_are_hashseed_stable() -> None:
    reports: dict[str, JsonValue] = hashseed_probe_reports(
        families=("connector_peer_missing_metadata",)
    )
    fault: JsonValue = reports["connector_peer_missing_metadata_fault"]
    control: JsonValue = reports["connector_peer_missing_metadata_control"]
    part_id_fault: JsonValue = reports["connector_peer_missing_metadata_part_id_fault"]
    part_id_control: JsonValue = reports["connector_peer_missing_metadata_part_id_control"]

    assert isinstance(fault, dict)
    assert isinstance(control, dict)
    assert isinstance(part_id_fault, dict)
    assert isinstance(part_id_control, dict)
    fault_report: dict[str, JsonValue] = fault
    control_report: dict[str, JsonValue] = control
    part_id_fault_report: dict[str, JsonValue] = part_id_fault
    part_id_control_report: dict[str, JsonValue] = part_id_control
    assert fault_report.get("status") == "REVIEW"
    assert control_report.get("status") != "REVIEW"
    assert part_id_fault_report.get("status") == "REVIEW"
    assert part_id_control_report.get("status") != "REVIEW"

    fault_findings_value: JsonValue = fault_report.get("findings")
    control_findings_value: JsonValue = control_report.get("findings")
    part_id_fault_findings_value: JsonValue = part_id_fault_report.get("findings")
    part_id_control_findings_value: JsonValue = part_id_control_report.get("findings")
    assert isinstance(fault_findings_value, list)
    assert isinstance(control_findings_value, list)
    assert isinstance(part_id_fault_findings_value, list)
    assert isinstance(part_id_control_findings_value, list)
    fault_findings: list[JsonValue] = fault_findings_value
    control_findings: list[JsonValue] = control_findings_value
    part_id_fault_findings: list[JsonValue] = part_id_fault_findings_value
    part_id_control_findings: list[JsonValue] = part_id_control_findings_value
    assert _matching_rule_findings(fault_findings)
    assert not _matching_rule_findings(control_findings)
    part_id_rule_findings = _matching_rule_findings(part_id_fault_findings)
    assert len(part_id_rule_findings) == 1
    evidence_value: JsonValue = part_id_rule_findings[0].get("evidence")
    assert isinstance(evidence_value, dict)
    evidence: dict[str, JsonValue] = evidence_value
    assert evidence.get("peer_identity_basis") == ["part_id"]
    assert not _matching_rule_findings(part_id_control_findings)
