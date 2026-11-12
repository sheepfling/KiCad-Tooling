"""Pinned KiCad proof that duplicate PCB DRC severity keys are order-sensitive."""

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
from kicad_tooling.hwrepo.pcb_drc_duplicate_severity_key_review import (
    source_bound_pcb_drc_duplicate_severity_key_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.drc_duplicate_severity_key"),
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
BOARD = Path(__file__).parent / "fixtures/design_lint/pcb-reference-zone-island/fault.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-severity-key"


def _track_dangling_results(tmp_path: Path, case: str, repeat: str) -> tuple[str, ...]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    board = work / "board.kicad_pcb"
    shutil.copyfile(BOARD, board)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pro", work / "board.kicad_pro")
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
        home_directory=f"pcb-drc-duplicate-severity-{case}-{repeat}",
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
    candidates = source_bound_pcb_drc_duplicate_severity_key_candidates(
        work,
        config,
        {"board.kicad_pro": digest(work / "board.kicad_pro")},
    )
    if case.startswith("fault-"):
        assert tuple(item.rule_id for item in candidates) == ("pcb.drc_duplicate_severity_key",)
    else:
        assert candidates == ()
    return tuple(
        sorted(
            str(item["severity"])
            for item in report["violations"]
            if item.get("type") == "track_dangling"
        )
    )


def test_kicad_1008_uses_last_duplicate_drc_severity_repeatably(tmp_path: Path) -> None:
    results = {
        case: tuple(_track_dangling_results(tmp_path, case, repeat) for repeat in ("a", "b"))
        for case in ("fault-ignore-last", "fault-warning-last", "control-unique-warning")
    }

    assert results["fault-ignore-last"] == ((), ())
    assert all(items and set(items) == {"warning"} for items in results["fault-warning-last"])
    assert all(items and set(items) == {"warning"} for items in results["control-unique-warning"])
