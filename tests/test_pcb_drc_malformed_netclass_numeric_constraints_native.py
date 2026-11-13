"""Pinned KiCad 10.0.8 behavior for malformed numeric netclass constraints."""

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
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_numeric_constraints_review import (
    source_bound_pcb_malformed_netclass_numeric_constraint_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "pcb.drc_malformed_netclass_numeric_constraints"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
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
    "fault-netclass-clearance-type-array",
    "fault-netclass-clearance-type-boolean",
    "fault-netclass-clearance-type-null",
    "fault-netclass-clearance-type-object",
    "fault-netclass-clearance-type-string",
)
CONTROL_CASES = (
    "control-netclass-clearance-default-assignment",
    "control-netclass-clearance-narrower-default",
    "control-netclass-clearance-property-omitted",
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
        home_directory=f"pcb-drc-malformed-constraint-{case}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kicad_version"] == VERSION

    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=Path("board.kicad_pro"),
            kicad_version=VERSION,
        ),
    )
    candidates = source_bound_pcb_malformed_netclass_numeric_constraint_candidates(
        work,
        config,
        {"board.kicad_pro": digest(settings)},
    )
    return (
        tuple(sorted(str(item["type"]) for item in report["violations"])),
        bool(candidates),
    )


def test_malformed_clearance_values_fall_back_like_default_and_repeat_with_narrow_control(
    tmp_path: Path,
) -> None:
    results = {
        case: tuple(_export_case(tmp_path, case, repeat) for repeat in ("a", "b"))
        for case in (*FAULT_CASES, *CONTROL_CASES)
    }

    for repeated in results.values():
        assert repeated[0] == repeated[1]
    default_violations, default_candidate = results[
        "control-netclass-clearance-default-assignment"
    ][0]
    narrow_violations, narrow_candidate = results["control-netclass-clearance-narrower-default"][0]
    omitted_violations, omitted_candidate = results["control-netclass-clearance-property-omitted"][
        0
    ]
    assert not default_candidate
    assert not narrow_candidate
    assert not omitted_candidate
    assert "clearance" not in default_violations
    assert "clearance" in narrow_violations
    assert omitted_violations == default_violations
    for case in FAULT_CASES:
        violations, has_candidate = results[case][0]
        assert has_candidate
        assert violations == default_violations
