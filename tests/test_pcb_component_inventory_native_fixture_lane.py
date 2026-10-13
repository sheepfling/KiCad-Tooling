"""Digest-pinned native acceptance for schematic-to-PCB inventory controls."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.ci_hosted_pcb_component_inventory_fixture import (
    pcb_component_inventory_fixture_lane,
)
from kicad_tooling.hwrepo.electrical import selected_config
from tests.pcb_native_fixture_support import (
    NATIVE_KICAD_PROJECTS,
    copy_reference_checkout,
    lane_event,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
@pytest.mark.design_lint_rule(rule_id="pcb.board_only_footprint")
def test_native_component_inventory_fault_and_control_are_source_bound(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-component-inventory-{project}")

    pcb_component_inventory_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-component-inventory-fixture/screen")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["fault_missing_references"] == "U2"
    assert result["control_missing_references"] == ""
    assert result["native_netlist_and_board_evidence"] == "true"
    assert result["repeated_evidence"] == "stable"
    assert len(result["fault_schematic_sha256"]) == 64
    assert len(result["control_schematic_sha256"]) == 64
    assert len(result["board_sha256"]) == 64
    assert result["fault_receipt"] != result["control_receipt"]

    identity = lane_event(log, "pcb-component-inventory-fixture/footprint-identity")
    assert identity["status"] == "PASS"
    assert identity["kicad_version"] == version
    assert identity["fault_mismatch_references"] == "U1"
    assert identity["control_mismatch_references"] == ""
    assert identity["fault_assigned_footprint"] == "Synthetic:Wrong_Footprint"
    assert identity["fault_placed_footprint"] == "Synthetic:Probe_Module"
    assert identity["control_assigned_footprint"] == "Synthetic:Probe_Module"
    assert identity["control_placed_footprint"] == "Synthetic:Probe_Module"
    assert identity["native_netlist_and_board_evidence"] == "true"
    assert identity["repeated_evidence"] == "stable"
    assert len(identity["fault_schematic_sha256"]) == 64
    assert len(identity["control_schematic_sha256"]) == 64
    assert len(identity["board_sha256"]) == 64
    assert identity["fault_receipt"] != identity["control_receipt"]

    population = lane_event(log, "pcb-component-population-fixture/screen")
    assert population["status"] == "PASS"
    assert population["kicad_version"] == version
    assert population["board_only_dnp"] == "U1"
    assert population["schematic_only_dnp"] == "U1"
    assert population["both_fitted"] == ""
    assert population["both_dnp"] == ""
    assert population["native_evidence_repeated"] == "true"
    source_hashes = json.loads(population["source_hashes"])
    assert set(source_hashes) == {
        "board-only-dnp.board",
        "board-only-dnp.schematic",
        "both-dnp.board",
        "both-dnp.schematic",
        "both-fitted.board",
        "both-fitted.schematic",
        "schematic-only-dnp.board",
        "schematic-only-dnp.schematic",
    }
    assert all(len(value) == 64 for value in source_hashes.values())

    values = lane_event(log, "pcb-component-value-fixture/screen")
    assert values["status"] == "PASS"
    assert values["kicad_version"] == version
    assert values["fault_mismatch_references"] == "U1"
    assert values["control_mismatch_references"] == ""
    assert values["fault_schematic_value"] == "Synthetic identity probe"
    assert values["fault_board_value"] == "Stale synthetic board value"
    assert values["control_schematic_value"] == "Synthetic identity probe"
    assert values["control_board_value"] == "Synthetic identity probe"
    assert values["repeated_native_evidence"] == "stable"
    value_source_hashes = json.loads(values["source_hashes"])
    assert set(value_source_hashes) == {
        "control.board",
        "control.schematic",
        "fault.board",
        "fault.schematic",
    }
    assert all(len(value) == 64 for value in value_source_hashes.values())

    board_only = lane_event(log, "pcb-board-only-footprint-fixture/screen")
    assert board_only["status"] == "PASS"
    assert board_only["kicad_version"] == version
    assert board_only["candidate_reference"] == "J2"
    assert board_only["native_netlist_and_board_evidence"] == "true"
    assert board_only["repeated_evidence"] == "stable"
    assert len(board_only["schematic_sha256"]) == 64
    assert len(board_only["board_sha256"]) == 64
    assert len(board_only["snapshot_sha256"]) == 64
