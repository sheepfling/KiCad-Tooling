"""Exact KiCad fixture checks for unanchored reference-zone review evidence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    pcb_reference_zone_island_fixture_lane,
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


@pytest.mark.design_lint_rule(rule_id="pcb.reference_plane_unanchored_island")
@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_unanchored_reference_island_fault_control_repeats(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-reference-island-{project}")

    pcb_reference_zone_island_fixture_lane(root, project=project, image=config.image, log=log)

    result = lane_event(log, "pcb-reference-plane-fixture/unanchored-island")
    assert result["status"] == "PASS"
    assert result["kicad_version"] == version
    assert result["fault_unanchored_islands"] == "1"
    assert result["control_unanchored_islands"] == "none"
    assert result["drc_unconnected_items"] == "0"
    assert set(result["drc_violation_types"].split(",")) == {
        "lib_footprint_issues",
        "track_dangling",
    }
    assert result["repeatable"] == "true"
    assert (root / result["fault_receipt"]).exists()
    assert (root / result["control_receipt"]).exists()
