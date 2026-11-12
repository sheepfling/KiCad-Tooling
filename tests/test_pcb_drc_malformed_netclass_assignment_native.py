"""Pinned KiCad 10.0.8 behavior for malformed netclass assignment shapes."""

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
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_assignment_review import (
    source_bound_pcb_malformed_netclass_assignment_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.drc_malformed_netclass_assignment"),
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]

VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
BOARD = FIXTURES / "board.kicad_pcb"
FAULT_CASES = (
    "fault-netclass-assignment-array-nonstring",
    "fault-netclass-assignment-value-number",
    "fault-netclass-assignment-map-array",
)
CONTROL_CASES = (
    "control-netclass-assignment-default",
    "control-netclass-assignment-array-narrow",
)


def _export_case(tmp_path: Path, case: str, repeat: str) -> tuple[tuple[str, ...], bool]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    board = work / "board.kicad_pcb"
    settings = work / "board.kicad_pro"
    shutil.copyfile(BOARD, board)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pro", settings)
    output = work / "drc.json"
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
            str(output),
            str(board),
        ),
        work,
        home_directory=f"pcb-drc-malformed-netclass-{case}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kicad_version"] == VERSION

    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB, project=Path("board.kicad_pro"), kicad_version=VERSION
        ),
    )
    candidates = source_bound_pcb_malformed_netclass_assignment_candidates(
        work,
        config,
        {"board.kicad_pro": digest(settings)},
    )
    return (
        tuple(sorted(str(item["type"]) for item in report["violations"])),
        bool(candidates),
    )


def test_malformed_shapes_fall_back_like_default_and_repeat_with_narrow_control(
    tmp_path: Path,
) -> None:
    results = {
        case: tuple(_export_case(tmp_path, case, repeat) for repeat in ("a", "b"))
        for case in (*FAULT_CASES, *CONTROL_CASES)
    }

    for repeated in results.values():
        assert repeated[0] == repeated[1]
    default_violations, default_candidate = results["control-netclass-assignment-default"][0]
    narrow_violations, narrow_candidate = results["control-netclass-assignment-array-narrow"][0]
    assert not default_candidate
    assert not narrow_candidate
    assert "clearance" in default_violations
    assert "clearance" not in narrow_violations
    for case in FAULT_CASES:
        violations, has_candidate = results[case][0]
        assert has_candidate
        assert violations == default_violations
