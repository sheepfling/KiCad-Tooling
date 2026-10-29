"""Cross-process hash-seed coverage for one-sided open I3C pins."""

from __future__ import annotations

import json

import pytest

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.i3c_unconnected_pin"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_i3c_unconnected_pin_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("i3c_unconnected_pin",))
    fault = DesignLintReport.model_validate_json(json.dumps(reports["i3c_unconnected_pin_fault"]))
    control = DesignLintReport.model_validate_json(
        json.dumps(reports["i3c_unconnected_pin_control"])
    )
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)

    assert tuple(item.subject for item in findings) == ("U1.1: I3C1_SDA",)
    assert not any(item.rule_id == RULE_ID for item in control.findings)
