"""Pinned KiCad behavior for a trailing PCB footprint instance path."""

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
from kicad_tooling.hwrepo.pcb_footprint_path_integrity import (
    pcb_footprint_path_trailing_separator_candidates,
)
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.footprint_path_trailing_separator"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-footprint-path-trailing-separator"
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


def _native_report(tmp_path: Path, version: str, case: str, repeat: str) -> dict:
    work = tmp_path / f"{version}-{case}-{repeat}"
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
        home_directory=f"pcb-footprint-path-{version}-{case}-{repeat}",
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
    candidates = pcb_footprint_path_trailing_separator_candidates(
        source_root,
        config,
        {BOARD: digest(board_path)},
    )
    assert tuple(candidate.rule_id for candidate in candidates) == (
        (RULE_ID,) if case == "fault" else ()
    )
    return report


def _native_semantics(report: dict) -> str:
    """Compare DRC outputs without unstable wrapper metadata."""
    return json.dumps(
        {
            "violations": report["violations"],
            "unconnected_items": report["unconnected_items"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_native_drc_does_not_distinguish_fault_from_complete_path(
    tmp_path: Path,
) -> None:
    for version in ("10.0.0", "10.0.5"):
        reports = {
            case: tuple(
                _native_semantics(_native_report(tmp_path, version, case, repeat))
                for repeat in ("a", "b")
            )
            for case in CASES
        }
        assert reports["fault"][0] == reports["fault"][1]
        assert reports["control"][0] == reports["control"][1]
        assert reports["fault"] == reports["control"]
