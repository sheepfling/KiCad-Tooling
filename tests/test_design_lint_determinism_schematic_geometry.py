"""Cross-process hash-seed checks for source-bound schematic geometry reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.schematic_lint,
]


def test_schematic_wire_crossing_fault_and_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("schematic_geometry",))
    assert set(reports) == {
        "schematic_wire_crossing_fault",
        "schematic_wire_crossing_junction_control",
    }
    fault = reports["schematic_wire_crossing_fault"]
    control = reports["schematic_wire_crossing_junction_control"]
    fault_geometry = fault["schematic_geometry"]
    control_geometry = control["schematic_geometry"]

    assert fault["netlist_sha256"] == control["netlist_sha256"]
    assert fault_geometry["source_sha256"] != control_geometry["source_sha256"]
    assert fault_geometry["status"] == control_geometry["status"] == "COMPLETE"
    assert fault["status"] == "REVIEW"
    assert fault_geometry["finding_count"] == 1
    assert len(fault["findings"]) == 1
    finding = fault["findings"][0]
    assert finding["rule_id"] == "schematic.unmarked_wire_crossing"
    assert finding["evidence"]["schematic_sha256"] == [fault_geometry["source_sha256"]]
    assert finding["evidence"]["crossing_mm"] == ["127.000000,127.000000"]
    assert control["status"] == "PASS"
    assert control_geometry["finding_count"] == 0
    assert control["findings"] == []
