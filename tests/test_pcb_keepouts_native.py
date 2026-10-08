"""Exact-version native extraction of synthetic PCB keepout rule areas."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    IgnoredChecks,
    PcbRuleAreaObservation,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.hwrepo.pcb_return_paths import capture_native_pcb_connectivity

pytestmark = pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
    reason="native PCB fixtures run in the digest-pinned package acceptance lane",
)

FIXTURE = Path(__file__).parent / "fixtures/design_lint/pcb-keepout-rule-area.kicad_pcb"


@pytest.mark.parametrize(
    ("expected_version", "image"),
    (
        (
            "10.0.0",
            (
                "ghcr.io/kicad/kicad:10.0.0@sha256:"
                "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
            ),
        ),
        (
            "10.0.5",
            (
                "ghcr.io/kicad/kicad:10.0.5@sha256:"
                "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
            ),
        ),
    ),
)
def test_native_rule_area_snapshot_records_exact_keepout_evidence(
    tmp_path: Path, expected_version: str, image: str
) -> None:
    root = tmp_path / "project"
    board_relative = "projects/synthetic/kicad/board.kicad_pcb"
    board = root / board_relative
    board.parent.mkdir(parents=True)
    board.write_bytes(FIXTURE.read_bytes())
    project_path = root / "projects/synthetic/kicad/board.kicad_pro"
    project_path.write_text("{}\n", encoding="utf-8")
    config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.PCB,
        assurance_profile="training",
        not_for_manufacture=True,
        project_id="synthetic-keepout",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id=f"kicad-{expected_version}",
        kicad_version=expected_version,
        image=image,
        project="projects/synthetic/kicad/board.kicad_pro",
        source_roots=("projects/synthetic",),
        required_inputs=(board_relative,),
        validation=PcbValidationContract(
            kind=ProjectKind.PCB,
            components={},
            nets={},
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
    )

    command, snapshot = capture_native_pcb_connectivity(
        root, config, root / "build/tests/native-keepout" / expected_version
    )

    assert command.returncode == 0, command.stderr or command.error
    assert snapshot is not None
    assert snapshot.kicad_version == expected_version
    assert snapshot.schema_version == "11"
    assert snapshot.board_sha256
    assert len(snapshot.rule_areas) == 1
    area: PcbRuleAreaObservation = snapshot.rule_areas[0]
    assert area.name == "SYNTHETIC_ANTENNA_KEEPOUT"
    assert area.layers == ("F.Cu", "B.Cu")
    assert area.net is None
    assert len(area.polygons) == 1
    assert set(area.polygons[0].outline_nm) == {
        (10_000_000, 10_000_000),
        (10_000_000, 12_000_000),
        (13_000_000, 12_000_000),
        (13_000_000, 10_000_000),
    }
    assert area.forbids_tracks
    assert area.forbids_vias
    assert area.forbids_pads
    assert area.forbids_zone_fills
    assert not area.forbids_footprints
