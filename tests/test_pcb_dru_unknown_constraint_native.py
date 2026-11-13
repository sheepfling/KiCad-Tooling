"""Pinned native behavior for unknown custom DRC constraint names."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]
RULE_ID = "pcb.custom_drc_unknown_constraint_type"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
VERSION = "10.0.8"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-unknown-constraint"
BOARD_FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings/board.kicad_pcb"
)
PROJECT_FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_lint/pcb-drc-duplicate-net-settings/control-netclass-clearance-default-assignment.kicad_pro"
)
CASES = {
    "fault": "fault-misspelled-track-width.kicad_dru",
    "control": "control-track-width.kicad_dru",
    "legacy_alias": "control-legacy-clearance-alias.kicad_dru",
    "canonical_alias_control": "control-physical-clearance.kicad_dru",
}


def _export_case(tmp_path: Path, case: str, fixture_name: str, repeat: str) -> tuple[str, ...]:
    work = tmp_path / f"{case}-{repeat}"
    fixture_dir = work / "fixtures"
    output_dir = work / "output"
    fixture_dir.mkdir(parents=True)
    output_dir.mkdir()
    shutil.copyfile(BOARD_FIXTURE, fixture_dir / "board.kicad_pcb")
    shutil.copyfile(PROJECT_FIXTURE, fixture_dir / "board.kicad_pro")
    shutil.copyfile(FIXTURES / fixture_name, fixture_dir / "board.kicad_dru")
    report_path = output_dir / "drc.json"

    command = execute_kicad_cli(
        IMAGE,
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            str(report_path),
            str(fixture_dir / "board.kicad_pcb"),
        ),
        work,
        home_directory=f"pcb-dru-unknown-constraint-{case}-{repeat}",
        fixture_directory=fixture_dir,
        output_directory=output_dir,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 5, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == VERSION
    return tuple(
        sorted(
            f"{item.get('type')}|{item.get('severity')}|{item.get('description')}"
            for item in report.get("violations", ())
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_misspelled_constraint_is_silently_skipped_and_control_is_repeatable(
    tmp_path: Path,
) -> None:
    results = {
        case: (
            _export_case(tmp_path, case, fixture, "first"),
            _export_case(tmp_path, case, fixture, "repeat"),
        )
        for case, fixture in CASES.items()
    }
    for first, repeat in results.values():
        assert first == repeat
    fault = results["fault"][0]
    control = results["control"][0]
    assert tuple(item.split("|", 1)[0] for item in fault) == (
        "track_dangling",
        "track_dangling",
    )
    widths = tuple(item for item in control if item.startswith("track_width|"))
    assert len(widths) == 2
    assert all("rule 'TrackWidthControl'" in item for item in widths)

    legacy = tuple(
        "|".join(item.split("|")[:2])
        for item in results["legacy_alias"][0]
        if item.startswith("clearance|")
    )
    canonical = tuple(
        "|".join(item.split("|")[:2])
        for item in results["canonical_alias_control"][0]
        if item.startswith("clearance|")
    )
    assert legacy
    assert legacy == canonical
