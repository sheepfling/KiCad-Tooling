"""Pinned native KiCad behavior for unassigned copper pads in mixed-net footprints."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_unassigned_copper_pad import unassigned_copper_pad_candidates
from tests.design_lint_fixtures.pcb_component_inventory import netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.unassigned_copper_pad_review"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-unassigned-copper-pad"
BOARD = "projects/synthetic/controller.kicad_pcb"
PROJECT = "projects/synthetic/controller.kicad_pro"
CASES = ("fault", "control")
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _native_report(tmp_path: Path, version: str, case: str) -> dict:
    work = tmp_path / f"{version}-{case}"
    work.mkdir()
    output = work / "output"
    output.mkdir()
    report_path = output / "drc.json"
    command = execute_kicad_cli(
        PINNED_NATIVE_KICAD_IMAGES[version],
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            str(report_path),
            str(FIXTURES / f"{case}.kicad_pcb"),
        ),
        work,
        home_directory=f"unassigned-copper-pad-{version}-{case}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == version

    source_root = work / "source"
    board_path = source_root / BOARD
    board_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT, kicad_version=version),
    )
    candidates = unassigned_copper_pad_candidates(
        source_root,
        config,
        {BOARD: digest(board_path)},
        netlist(
            components={"J1": "Synthetic:TwoPadConnector"},
            nets={"SIGNAL": ("J1.1",)},
            component_pin_numbers={"J1": ("1",)},
        ),
    )
    assert tuple(candidate.rule_id for candidate in candidates) == (
        (RULE_ID,) if case == "fault" else ()
    )
    return report


def _native_semantics(report: dict) -> str:
    return json.dumps(
        {
            "violations": report["violations"],
            "unconnected_items": report["unconnected_items"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_native_drc_does_not_distinguish_unassigned_pad_fault_from_control(
    tmp_path: Path,
) -> None:
    for version in ("10.0.0", "10.0.5"):
        reports = {case: _native_report(tmp_path, version, case) for case in CASES}
        assert reports["fault"]["unconnected_items"] == []
        assert reports["control"]["unconnected_items"] == []
        for report in reports.values():
            assert [item["type"] for item in report["violations"]] == ["lib_footprint_issues"]
            assert "Synthetic" in report["violations"][0]["description"]
        assert _native_semantics(reports["fault"]) == _native_semantics(reports["control"])
