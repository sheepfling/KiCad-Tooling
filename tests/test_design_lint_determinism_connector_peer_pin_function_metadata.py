"""Cross-process hash-seed regression for peer function metadata review."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import JsonValue

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

RULE_ID = "connector.footprint_peer_pin_function_metadata_incomplete"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report_object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError("hash-seed probe report must be an object")
    return cast(JsonObject, value)


def _findings(report: JsonObject) -> list[JsonObject]:
    value = report.get("findings")
    if not isinstance(value, list):
        raise TypeError("hash-seed probe findings must be an array")
    return [cast(JsonObject, item) for item in value if isinstance(item, dict)]


def test_fault_and_control_reports_are_stable_across_hash_seed_processes() -> None:
    reports = hashseed_probe_reports(families=("connector_peer_pin_function_metadata",))
    fault = _report_object(reports["connector_peer_pin_function_metadata_fault"])
    control = _report_object(reports["connector_peer_pin_function_metadata_control"])
    fault_findings = [item for item in _findings(fault) if item.get("rule_id") == RULE_ID]
    control_findings = [item for item in _findings(control) if item.get("rule_id") == RULE_ID]

    assert fault.get("status") == "REVIEW"
    assert len(fault_findings) == 1
    assert control.get("status") == "PASS"
    assert control_findings == []
