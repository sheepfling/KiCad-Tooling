"""Digest-pinned KiCad snapshots for the mapped track-angle geometry cross-check."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import repo_path
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.pcb_return_path_capture import capture_native_pcb_connectivity_result
from kicad_tooling.hwrepo.pcb_track_angle_geometry import track_angle_geometry_violations
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from tests.pcb_native_fixture_support import NATIVE_KICAD_PROJECTS, copy_reference_checkout

RULE_ID = "pcb.track_angle_geometry_review"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-track-angle"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_TRACK_ANGLE_GEOMETRY_FIXTURES") != "1",
        reason="track-angle geometry snapshots require digest-pinned KiCad containers",
    ),
]


def _angle_map() -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Tooling-owned synthetic geometry acceptance",
        requirements=(
            PcbTrackAngleRequirement(
                id="clock-output",
                basis="Synthetic minimum for the native fault/control fixture",
                net="CLOCK_OUT",
                rule_name="clock-track-angle",
                minimum_degrees=150,
            ),
        ),
    )


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_snapshot_angle_matches_synthetic_fault_and_control(
    tmp_path: Path, project: str, version: str
) -> None:
    requirement = _angle_map()
    observations = {}
    for case in ("fault", "control"):
        root = copy_reference_checkout(tmp_path / case)
        config = selected_config(root, project)
        assert config.kicad_version == version
        board = repo_path(root, config.project).with_suffix(".kicad_pcb")
        shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board)
        output = root / "build" / "track-angle-geometry" / project / case
        capture = capture_native_pcb_connectivity_result(root, config, output)
        assert capture.command.error is None, capture.command.model_dump_json(indent=2)
        assert capture.command.returncode == 0, capture.command.model_dump_json(indent=2)
        assert capture.snapshot is not None
        observations[case] = track_angle_geometry_violations(requirement, capture.snapshot)

    assert len(observations["fault"]) == 1
    assert observations["fault"][0].angle_millidegrees == 135_000
    assert observations["fault"][0].requirement.net == "CLOCK_OUT"
    assert observations["control"] == ()
