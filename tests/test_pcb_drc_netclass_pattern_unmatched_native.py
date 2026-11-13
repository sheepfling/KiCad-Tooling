"""Pinned KiCad 10.0.8 behavior for unmatched PCB netclass patterns."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.drc_netclass_pattern_unmatched"),
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
CASES = {
    "fault-unmatched": False,
    "fault-case-mismatch": False,
    "control-literal": True,
    "control-wildcard": True,
    "control-regex": True,
}


def _clearance_result(tmp_path: Path, case: str, repeat: str) -> tuple[str, ...]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    shutil.copyfile(BOARD, work / "board.kicad_pcb")
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
            str(work / "board.kicad_pcb"),
        ),
        work,
        home_directory=f"pcb-drc-unmatched-netclass-{case}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kicad_version"] == VERSION
    return tuple(sorted(str(item["type"]) for item in report["violations"]))


def test_unmatched_patterns_fall_back_while_literal_wildcard_and_regex_match(
    tmp_path: Path,
) -> None:
    results = {
        case: tuple(_clearance_result(tmp_path, case, repeat) for repeat in ("a", "b"))
        for case in CASES
    }

    for repeated in results.values():
        assert repeated[0] == repeated[1]
    assert "clearance" not in results["fault-unmatched"][0]
    for control in ("control-literal", "control-wildcard", "control-regex"):
        assert "clearance" in results[control][0]
