"""Digest-pinned native acceptance for the PCB decoupling fixture."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.ci_hosted_pcb_decoupling_fixture import decoupling_placement_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.pcb_native_fixture_support import (
    NATIVE_KICAD_PROJECTS,
    copy_reference_checkout,
    lane_event,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_decoupling_controls_on_supported_kicad(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-decoupling-{project}")

    decoupling_placement_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-decoupling-fixture/placement")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["near_distance_nm"] == 1_000_000
    assert result["distant_distance_nm"] == 15_000_000
    assert result["connected_return_via_distance_nm"] == 1_000_000
    assert result["distant_return_via_fault_distance_nm"] == 2_000_000
    assert result["repeatable"] == "true"
