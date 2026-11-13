"""Pinned native DRC evidence for contradictory custom rule bounds."""

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
RULE_ID = "pcb.custom_drc_contradictory_constraint_bounds"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
VERSION = "10.0.8"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-contradictory-bounds"
SOURCE_FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
BOARD_FIXTURE = SOURCE_FIXTURES / "board.kicad_pcb"
PROJECT_FIXTURE = SOURCE_FIXTURES / "control-netclass-clearance-default-assignment.kicad_pro"
CASES = {
    "fault-min-exceeds-max": "fault-min-exceeds-max.kicad_dru",
    "control-valid-range": "control-valid-range.kicad_dru",
    "control-equal-bounds": "control-equal-bounds.kicad_dru",
}


def _export_case(
    tmp_path: Path,
    case: str,
    fixture_name: str,
    repeat: str,
) -> tuple[str, ...]:
    work = tmp_path / f"{case}-{repeat}"
    fixture_dir = work / "fixtures"
    output_dir = work / "output"
    fixture_dir.mkdir(parents=True)
    output_dir.mkdir()
    board = fixture_dir / "board.kicad_pcb"
    project = fixture_dir / "board.kicad_pro"
    rules = fixture_dir / "board.kicad_dru"
    shutil.copyfile(BOARD_FIXTURE, board)
    shutil.copyfile(PROJECT_FIXTURE, project)
    shutil.copyfile(FIXTURES / fixture_name, rules)
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
            "--output",
            str(report_path),
            str(board),
        ),
        work,
        home_directory=f"pcb-dru-contradictory-bounds-{case}-{repeat}",
        fixture_directory=fixture_dir,
        output_directory=output_dir,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == VERSION
    return tuple(
        sorted(
            f"{item.get('type')}|{item.get('severity')}|{item.get('description')}"
            for item in report.get("violations", ())
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_contradictory_bounds_are_accepted_and_produce_native_width_findings_repeatably(
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
    fault = results["fault-min-exceeds-max"][0]
    assert sum(item.startswith("track_width|error|") for item in fault) == 2
    assert all("SyntheticWidthRange" in item for item in fault if item.startswith("track_width|"))
    assert all("min width 0.1000 mm" in item for item in fault if item.startswith("track_width|"))
    for control in ("control-valid-range", "control-equal-bounds"):
        assert not any(item.startswith("track_width|") for item in results[control][0])
