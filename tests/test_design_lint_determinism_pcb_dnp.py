"""Hash-seed regressions for schematic/PCB DNP mismatch reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_dnp_mismatch_directions_and_fitted_control_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_dnp_mismatch",))
    board_only = reports["pcb_dnp_board_only_mismatch"]
    schematic_only = reports["pcb_dnp_schematic_only_mismatch"]
    fitted_control = reports["pcb_dnp_fitted_control"]

    assert board_only["netlist_sha256"] == fitted_control["netlist_sha256"]
    assert board_only["board_sha256"] != fitted_control["board_sha256"]
    assert board_only["snapshot_sha256"] != fitted_control["snapshot_sha256"]
    assert schematic_only["netlist_sha256"] != fitted_control["netlist_sha256"]
    assert schematic_only["board_sha256"] == fitted_control["board_sha256"]
    assert schematic_only["snapshot_sha256"] == fitted_control["snapshot_sha256"]

    for case, expected_schematic_dnp, expected_board_dnp in (
        (board_only, "false", "true"),
        (schematic_only, "true", "false"),
    ):
        report = case["report"]
        assert report["status"] == "REVIEW"
        assert report["netlist_sha256"] == case["netlist_sha256"]
        inventory = report["pcb_component_inventory"]
        assert inventory["board_sha256"] == case["board_sha256"]
        assert inventory["snapshot_sha256"] == case["snapshot_sha256"]
        assert inventory["population_mismatches"][0]["schematic_dnp"] == (
            expected_schematic_dnp == "true"
        )
        assert inventory["population_mismatches"][0]["board_dnp"] == (expected_board_dnp == "true")
        assert [item["rule_id"] for item in report["findings"]] == [
            "pcb.schematic_pcb_dnp_mismatch"
        ]
        assert report["findings"][0]["mode"] == "review"
        assert report["findings"][0]["evidence"]["schematic_dnp"] == [expected_schematic_dnp]
        assert report["findings"][0]["evidence"]["board_dnp"] == [expected_board_dnp]

    control = fitted_control["report"]
    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == fitted_control["netlist_sha256"]
    assert control["pcb_component_inventory"]["population_mismatches"] == []
    assert control["findings"] == []
