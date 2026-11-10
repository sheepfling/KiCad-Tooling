"""Digest-pinned native KiCad acceptance for board fiducial-count lint."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_fiducial_fixture_lane
from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from tests.pcb_native_fixture_support import lane_event

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


@pytest.mark.parametrize(
    "version,image",
    KICAD_10_NATIVE_TOOLCHAINS,
    ids=lambda value: value,
)
def test_native_fault_and_control_are_source_bound(
    tmp_path: Path, version: str, image: str
) -> None:
    root = tmp_path / "synthetic-project"
    log = HostedLog(root, f"native-pcb-fiducial-{version}")

    pcb_fiducial_fixture_lane(root, project=f"synthetic-{version}", image=image, log=log)

    result = lane_event(log, "pcb-fiducial-fixture/board-count")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["fitted_exact_matches"] == 1
    assert result["fault_minimum"] == 2
    assert result["control_minimum"] == 1
    assert result["fault_status"] == "INCOMPLETE"
    assert result["control_status"] == "COMPLETE"
    assert result["dnp_excluded"] == "true"
    assert result["unrelated_footprint_excluded"] == "true"
    assert result["repeatable"] == "true"
    assert (root / result["receipt"]).exists()
