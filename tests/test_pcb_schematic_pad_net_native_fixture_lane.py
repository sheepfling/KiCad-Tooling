"""Digest-pinned native acceptance for schematic-to-PCB pad net assignments."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.ci_hosted_pcb_pad_net_fixture import (
    pcb_schematic_pcb_pad_net_fixture_lane,
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
def test_native_schematic_pcb_pad_net_fault_and_control_are_source_bound(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-pad-net-{project}")

    pcb_schematic_pcb_pad_net_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-schematic-pcb-pad-net-fixture/screen")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["fault_findings"] == "U1.1: schematic and PCB net assignments differ"
    assert result["control_findings"] == ""
    assert result["repeated_native_evidence"] == "stable"
    source_hashes = json.loads(result["source_hashes"])
    assert set(source_hashes) == {
        "control.board",
        "control.schematic",
        "fault.board",
        "fault.schematic",
    }
    assert all(len(value) == 64 for value in source_hashes.values())
