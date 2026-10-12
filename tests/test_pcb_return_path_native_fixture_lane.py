"""Digest-pinned native acceptance for PCB return-path fixture cases."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_return_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.pcb_native_fixture_support import (
    NATIVE_KICAD_PROJECTS,
    copy_reference_checkout,
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

EXPECTED_CONNECTIVITY = {
    "alternate-layer-via": "connected",
    "alternate-layer-open": "open",
    "zone-connected": "connected",
    "unstitched-planes": "open",
    "stitched-planes": "connected",
    "zone-unanchored-island": "connected",
    "zone-split": "open",
    "zone-through-hole-split": "open",
    "net-tie-connected": "connected",
    "net-tie-dnp": "open",
    "isolation-open": "connected",
    "isolation-bridged": "connected",
}


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS, ids=lambda value: value)
def test_native_return_path_fixture_cases_on_supported_kicad(
    tmp_path: Path, project: str, version: str
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-return-{project}")

    pcb_return_fixture_lane(root, project=project, image=config.image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"].removeprefix("pcb-return-fixture/"): item
        for item in events
        if item.get("stage", "").startswith("pcb-return-fixture/")
    }
    assert set(results) == set(EXPECTED_CONNECTIVITY)
    for fixture_id, expected_connectivity in EXPECTED_CONNECTIVITY.items():
        result = results[fixture_id]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["expected_connectivity"] == expected_connectivity
        assert (root / result["receipt"]).exists()
        if fixture_id == "alternate-layer-via":
            assert result["via_identity_repeatable"] == "true"
        if fixture_id == "stitched-planes":
            assert result["plane_stitch_repeatable"] == "true"
            assert result["zone_layers"] == "F.Cu,B.Cu"
        if fixture_id.startswith("isolation-"):
            assert result["expected_isolation"] == (
                "separate" if fixture_id == "isolation-open" else "bridged"
            )
