"""Digest-pinned native evidence for named schematic/PCB population variants."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog
from kicad_tooling.ci_hosted_pcb_variant_population_fixture import (
    pcb_variant_population_fixture_lane,
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
def test_native_named_variant_population_faults_and_control_are_source_bound(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    root = copy_reference_checkout(tmp_path / "repository")
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-pcb-variant-population-{project}")

    pcb_variant_population_fixture_lane(root, project=project, image=config.image, log=log)

    event = lane_event(log, "pcb-variant-population-fixture/screen")
    assert event["status"] == "PASS"
    assert event["kicad_version"] == version
    assert event["variant"] == "Synthetic Assembly A"
    assert event["board_only_dnp"] == "U1"
    assert event["schematic_only_dnp"] == "U1"
    assert event["both_fitted_mismatches"] == ""
    assert event["missing_board_variant_blocked"] == "true"
    assert event["board_variant_presence_probed"] == "true"
    source_hashes = json.loads(event["source_hashes"])
    assert len(source_hashes) == 12
    assert all(len(value) == 64 for value in source_hashes.values())
    export_hashes = json.loads(event["native_export_hashes"])
    assert set(export_hashes) == {"board-only-dnp", "schematic-only-dnp", "both-fitted"}
    assert all(len(value) == 64 for case in export_hashes.values() for value in case.values())
    probe_hashes = json.loads(event["board_variant_probe_hashes"])
    assert set(probe_hashes) == {
        "board-only-dnp",
        "schematic-only-dnp",
        "both-fitted",
        "board-missing-variant",
    }
    assert all(len(value) == 64 for value in probe_hashes.values())
