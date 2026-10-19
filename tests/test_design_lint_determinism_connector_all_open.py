"""Cross-process determinism for the generic connector all-open prompt."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.connector_lint]


def test_generic_connector_all_open_reports_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("connector_peer_pins",))
    fault = reports["connector_generic_peer_pin_all_open_fault"]
    control = reports["connector_generic_peer_pin_all_open_control"]

    assert fault["status"] == "REVIEW"
    assert control["status"] == "PASS"
    assert fault["netlist_sha256"] != control["netlist_sha256"]
    assert [item["rule_id"] for item in fault["findings"]] == [
        "connector.generic_peer_pin_all_open"
    ]
    assert control["findings"] == []

    fault_coverage = fault["connector_peer_pin_coverage"]
    control_coverage = control["connector_peer_pin_coverage"]
    assert fault_coverage["generic_peer_pin_all_open_finding_count"] == 1
    assert control_coverage["generic_peer_pin_all_open_finding_count"] == 0
    assert fault["findings"][0]["mode"] == "review"
    assert fault["findings"][0]["evidence"]["J1.2"] == []
    assert fault["findings"][0]["evidence"]["shared_anchor_contacts"] == [
        "J1.1 / J2.1 / J3.1 -> +5V"
    ]
