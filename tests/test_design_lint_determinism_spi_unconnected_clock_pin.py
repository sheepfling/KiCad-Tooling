"""Cross-process hash-seed coverage for open SPI clock findings."""

from __future__ import annotations

import json

import pytest

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

RULE_ID = "bus.spi_unconnected_clock_pin"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_spi_unconnected_clock_reports_are_hashseed_deterministic() -> None:
    reports = hashseed_probe_reports(families=("spi_unconnected_clock_pin",))
    fault = DesignLintReport.model_validate_json(
        json.dumps(reports["spi_unconnected_clock_pin_fault"])
    )
    control = DesignLintReport.model_validate_json(
        json.dumps(reports["spi_unconnected_clock_pin_control"])
    )
    findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    assert tuple(item.subject for item in findings) == ("U1.1: SCK",)
    assert not any(item.rule_id == RULE_ID for item in control.findings)
