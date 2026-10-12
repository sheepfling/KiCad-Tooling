"""Digest-pinned native acceptance for reference-plane geometry fixtures."""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    pcb_reference_plane_narrow_void_fixture_lane,
    pcb_reference_plane_via_fixture_lane,
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
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_via_antipad_fault_control_repeats(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-reference-via-{project}")

    pcb_reference_plane_via_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-reference-plane-fixture/via-antipad")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["fault_threshold"] == 0.75
    assert result["control_threshold"] == 0.5
    assert result["endpoint_via_hole_candidate"]
    assert result["intervals_remain_uncovered"] == "true"
    assert result["repeatable"] == "true"
    assert (root / result["receipt"]).exists()


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_narrow_void_fault_control_repeats(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-reference-narrow-void-{project}")

    pcb_reference_plane_narrow_void_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-reference-plane-fixture/narrow-void")
    control_fraction = Fraction(result["control_coverage"])
    fault_fraction = Fraction(result["fault_coverage"])
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["minimum_fraction"] == 0.65
    assert control_fraction >= Fraction("0.65")
    assert fault_fraction < Fraction("0.65")
    assert control_fraction > fault_fraction
    assert result["control_below_threshold"] == "false"
    assert result["fault_below_threshold"] == "true"
    assert result["endpoint_via_hole_context"] == "retained"
    assert result["repeatable"] == "true"
    assert (root / result["control_receipt"]).exists()
    assert (root / result["fault_receipt"]).exists()
