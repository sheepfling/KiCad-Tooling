"""Pinned KiCad proof for duplicate top-level schematic ERC sections."""

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
from kicad_tooling.hwrepo.schematic_erc_duplicate_section_review import (
    source_bound_schematic_erc_duplicate_section_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.erc_duplicate_section"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8@sha256:"
    "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
)
SCHEMATIC = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-duplicate-section"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_ERC_DUPLICATE_SECTION_FIXTURES") != "1",
        reason="native schematic ERC duplicate-section fixtures run in the digest-pinned acceptance lane",
    ),
]


def _run_erc(
    tmp_path: Path,
    case: str,
    repeat: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    project = work / "board.kicad_pro"
    schematic = work / "board.kicad_sch"
    shutil.copyfile(FIXTURES / f"{case}.kicad_pro", project)
    shutil.copyfile(SCHEMATIC, schematic)
    report_path = work / "erc.json"
    command = execute_kicad_cli(
        IMAGE,
        (
            "kicad-cli",
            "sch",
            "erc",
            "--format",
            "json",
            "--output",
            str(report_path),
            str(schematic),
        ),
        work,
        home_directory=f"schematic-erc-duplicate-section-{case}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["kicad_version"] == VERSION
    violations = tuple(
        violation
        for sheet in payload["sheets"]
        for violation in sheet["violations"]
        if violation.get("type") == "pin_not_connected"
    )
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=Path("board.kicad_pro"),
            kicad_version=VERSION,
        ),
    )
    candidates = source_bound_schematic_erc_duplicate_section_candidates(
        work,
        config,
        {"board.kicad_pro": digest(project)},
    )
    return (
        tuple(sorted(str(item["severity"]) for item in violations)),
        tuple(item.rule_id for item in candidates),
    )


@pytest.mark.parametrize(
    ("case", "expected_severities", "expected_candidates"),
    (
        (
            "fault-warning-ignore",
            (),
            ("schematic.erc_duplicate_section",),
        ),
        (
            "fault-ignore-warning",
            ("warning", "warning"),
            ("schematic.erc_duplicate_section",),
        ),
        ("control-warning", ("warning", "warning"), ()),
        ("control-ignore", (), ()),
    ),
)
def test_kicad_1008_uses_last_duplicate_erc_section_repeatably(
    tmp_path: Path,
    case: str,
    expected_severities: tuple[str, ...],
    expected_candidates: tuple[str, ...],
) -> None:
    runs = tuple(_run_erc(tmp_path, case, repeat) for repeat in ("first", "repeat"))

    assert all(severities == expected_severities for severities, _ in runs)
    assert all(candidates == expected_candidates for _, candidates in runs)
    assert runs[0] == runs[1]
