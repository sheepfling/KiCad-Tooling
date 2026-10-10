"""Hash-seed regressions for mapped PCB track-width reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_mapped_track_width_reports_remain_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_measurements",))
    fault_case = reports["pcb_track_width_fault"]
    control_case = reports["pcb_track_width_control"]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"]
    assert fault_case["board_sha256"] != control_case["board_sha256"]
    assert fault_case["snapshot_sha256"] != control_case["snapshot_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    assert fault["pcb_track_width"]["status"] == "COMPLETE"
    assert fault["pcb_track_width"]["entries"][0]["tracks"][0]["below_minimum"]
    assert "pcb.minimum_track_width" in {item["rule_id"] for item in fault["findings"]}

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    assert control["pcb_track_width"]["status"] == "COMPLETE"
    assert not control["pcb_track_width"]["entries"][0]["tracks"][0]["below_minimum"]
    assert control["findings"] == []
