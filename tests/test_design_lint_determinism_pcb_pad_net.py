"""Hash-seed regressions for schematic/PCB pad-net reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_pad_net_source_mutations_and_matching_control_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_pad_net_mismatch",))
    board_only = reports["pcb_pad_net_board_only_mismatch"]
    schematic_only = reports["pcb_pad_net_schematic_only_mismatch"]
    matching = reports["pcb_pad_net_matching_control"]

    assert board_only["netlist_sha256"] == matching["netlist_sha256"]
    assert board_only["board_sha256"] != matching["board_sha256"]
    assert board_only["snapshot_sha256"] != matching["snapshot_sha256"]
    assert schematic_only["netlist_sha256"] != matching["netlist_sha256"]
    assert schematic_only["board_sha256"] == matching["board_sha256"]
    assert schematic_only["snapshot_sha256"] == matching["snapshot_sha256"]

    for case, schematic_net, board_net in (
        (board_only, "SIGNAL", "BOARD_SIGNAL"),
        (schematic_only, "SCHEMATIC_SIGNAL", "SIGNAL"),
    ):
        report = case["report"]
        assert report["status"] == "REVIEW"
        assert report["netlist_sha256"] == case["netlist_sha256"]
        inventory = report["pcb_component_inventory"]
        assert inventory["pad_net_comparison_status"] == "COMPLETE"
        assert inventory["board_sha256"] == case["board_sha256"]
        assert inventory["snapshot_sha256"] == case["snapshot_sha256"]
        assert inventory["pad_net_mismatches"] == [
            {
                "reference": "U1",
                "pin": "1",
                "mismatch": "net_assignment_differs",
                "schematic_net": schematic_net,
                "board_net": board_net,
            }
        ]
        assert [item["rule_id"] for item in report["findings"]] == [
            "pcb.schematic_pcb_pad_net_mismatch"
        ]
        finding = report["findings"][0]
        assert finding["mode"] == "review"
        assert finding["evidence"]["mismatch"] == ["net_assignment_differs"]
        assert finding["evidence"]["schematic_net"] == [schematic_net]
        assert finding["evidence"]["board_net"] == [board_net]

    control = matching["report"]
    assert control["status"] == "PASS"
    assert control["pcb_component_inventory"]["pad_net_mismatches"] == []
    assert control["findings"] == []
