"""Pinned KiCad 10.0.8 behavior for conflicting netclass definitions."""

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
from kicad_tooling.hwrepo.pcb_drc_netclass_conflict_review import (
    source_bound_pcb_netclass_conflict_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.drc_conflicting_netclass_definitions"),
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
CASES = {
    "fault-netclass-list-narrow-last": (True, False),
    "fault-netclass-list-wide-last": (True, True),
    "fault-netclass-name-narrow-last": (True, False),
    "fault-netclass-name-wide-last": (True, True),
    "control-identical-netclass-list": (False, False),
    "control-unique-narrow": (False, False),
}


def _clearance_results(tmp_path: Path, case: str, repeat: str) -> tuple[str, ...]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    board = work / "board.kicad_pcb"
    settings = work / "board.kicad_pro"
    shutil.copyfile(FIXTURES / "board.kicad_pcb", board)
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
        home_directory=f"pcb-drc-netclass-conflict-{case}-{repeat}",
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
    candidates = source_bound_pcb_netclass_conflict_candidates(
        work,
        config,
        {"board.kicad_pro": digest(settings)},
    )
    expects_finding, _has_clearance = CASES[case]
    assert tuple(item.rule_id for item in candidates) == (
        ("pcb.drc_conflicting_netclass_definitions",) if expects_finding else ()
    )
    return tuple(sorted(str(item["type"]) for item in report["violations"]))


def test_kicad_1008_conflicting_netclass_definitions_are_order_sensitive_and_repeatable(
    tmp_path: Path,
) -> None:
    results = {
        case: tuple(_clearance_results(tmp_path, case, repeat) for repeat in ("a", "b"))
        for case in CASES
    }

    for repeated in results.values():
        assert repeated[0] == repeated[1]
    for case, (_has_finding, has_clearance) in CASES.items():
        assert ("clearance" in results[case][0]) is has_clearance
