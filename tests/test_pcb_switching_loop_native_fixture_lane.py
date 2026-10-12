"""Digest-pinned native acceptance for switching-loop geometry fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_switching_loop_fixture_lane
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
def test_native_switching_loop_geometry_fixtures(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-switching-loop-{project}")

    pcb_switching_loop_fixture_lane(root, project=project, image=config.image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    loop_results = tuple(
        item for item in events if item.get("stage", "").startswith("pcb-switching-loop-fixture/")
    )
    expected_stages = {
        "pcb-switching-loop-fixture/front-plane",
        "pcb-switching-loop-fixture/arc-trace",
        "pcb-switching-loop-fixture/inner-plane",
        "pcb-switching-loop-fixture/split-inner-plane",
    }
    assert {item["stage"] for item in loop_results} == expected_stages
    assert all(item["status"] == "PASS" for item in loop_results)
    assert all(item["kicad_version"] == version for item in loop_results)

    front_plane = lane_event(log, "pcb-switching-loop-fixture/front-plane")
    assert front_plane["resolved_trace_length_nm"] == 15_000_000
    assert int(front_plane["plane_contour_area_twice_nm2"]) > 0
    arc_trace = lane_event(log, "pcb-switching-loop-fixture/arc-trace")
    assert arc_trace["resolved_trace_length_nm"] == "UNSUPPORTED_ARC"
    assert int(arc_trace["plane_contour_area_twice_nm2"]) > 0
    inner_plane = lane_event(log, "pcb-reference-plane-fixture/inner-plane")
    assert inner_plane["status"] == "PASS"
    assert inner_plane["kicad_version"] == version
    assert inner_plane["covered_fraction"] == "4/15"
    assert inner_plane["fault_threshold"] == 0.3
    assert inner_plane["control_threshold"] == 0.25
    assert inner_plane["below_fault_threshold"] == "true"
    assert inner_plane["repeatable"] == "true"
