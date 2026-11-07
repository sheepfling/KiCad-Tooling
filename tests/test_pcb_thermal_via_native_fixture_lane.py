"""Digest-pinned native KiCad acceptance for thermal-pad via coverage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_thermal_via_fixture_lane
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
    pytest.mark.template_checkout,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_fault_and_control_are_source_bound(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-thermal-via-{project}")

    pcb_thermal_via_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-thermal-via-fixture/pad-count")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["connected_vias"] == 2
    assert result["fault_minimum"] == 3
    assert result["control_minimum"] == 2
    assert result["fault_status"] == "INCOMPLETE"
    assert result["control_status"] == "COMPLETE"
    assert result["repeatable"] == "true"
    assert (root / result["receipt"]).exists()
