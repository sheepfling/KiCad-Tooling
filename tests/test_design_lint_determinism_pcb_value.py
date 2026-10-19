"""Hash-seed regressions for schematic/PCB component value reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_value_mismatch_source_mutations_and_matching_control_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_value_mismatch",))
    board_only = reports["pcb_value_board_only_mismatch"]
    schematic_only = reports["pcb_value_schematic_only_mismatch"]
    matching = reports["pcb_value_matching_control"]

    assert board_only["netlist_sha256"] == matching["netlist_sha256"]
    assert board_only["board_sha256"] != matching["board_sha256"]
    assert board_only["snapshot_sha256"] != matching["snapshot_sha256"]
    assert schematic_only["netlist_sha256"] != matching["netlist_sha256"]
    assert schematic_only["board_sha256"] == matching["board_sha256"]
    assert schematic_only["snapshot_sha256"] == matching["snapshot_sha256"]

    for case, schematic_value, board_value in (
        (board_only, "10k", "10K"),
        (schematic_only, "22k", "10k"),
    ):
        report = case["report"]
        assert report["status"] == "REVIEW"
        assert report["netlist_sha256"] == case["netlist_sha256"]
        inventory = report["pcb_component_inventory"]
        assert inventory["value_comparison_status"] == "COMPLETE"
        assert inventory["board_sha256"] == case["board_sha256"]
        assert inventory["snapshot_sha256"] == case["snapshot_sha256"]
        assert inventory["value_mismatches"] == [
            {
                "reference": "R1",
                "schematic_value": schematic_value,
                "board_value": board_value,
            }
        ]
        assert [item["rule_id"] for item in report["findings"]] == [
            "pcb.schematic_pcb_value_mismatch"
        ]
        finding = report["findings"][0]
        assert finding["mode"] == "review"
        assert finding["evidence"]["schematic_value"] == [schematic_value]
        assert finding["evidence"]["board_value"] == [board_value]

    control = matching["report"]
    assert control["status"] == "PASS"
    assert control["pcb_component_inventory"]["value_mismatches"] == []
    assert control["findings"] == []
