"""Cross-process stability for JTAG connector return-role review reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

RULE_ID = "connector.jtag_pair_without_return_review"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _finding_rule_ids(report: JsonObject) -> set[str]:
    return {str(finding["rule_id"]) for finding in report["findings"]}


def test_jtag_connector_return_reports_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("jtag_connector_return",))
    fault = reports["jtag_connector_return_fault"]
    control = reports["jtag_connector_return_control"]

    assert fault["netlist_sha256"] != control["netlist_sha256"]
    assert "connector.jtag_pair_without_return_review" in _finding_rule_ids(fault)
    assert "connector.jtag_pair_without_return_review" not in _finding_rule_ids(control)
