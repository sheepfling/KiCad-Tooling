"""Digest-pinned native acceptance for schematic-to-PCB inventory controls."""

from __future__ import annotations

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
