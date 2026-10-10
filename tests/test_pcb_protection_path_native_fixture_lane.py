"""Digest-pinned native acceptance for connector protection-path controls."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.ci_hosted_pcb_protection_fixture import protection_path_fixture_lane
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
def test_native_protection_path_faults_on_supported_kicad(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-protection-{project}")

    protection_path_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-protection-path-fixture/entry")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["connector_to_protector_distance_nm"] == 650_000
    assert result["connected_reference_vias"] == 1
    assert result["distance_fault_limit_um"] == 649
    assert result["via_count_fault_minimum"] == 2
    assert result["nearby_reference_via_pad_distance_nm"] == 1_500_000
    assert result["connected_vias_for_nearby_open_fault"] == 0
    assert result["repeatable"] == "true"
