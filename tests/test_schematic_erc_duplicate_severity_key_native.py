"""Pinned KiCad proof for duplicate schematic ERC severity-map keys."""

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
from kicad_tooling.hwrepo.schematic_erc_duplicate_severity_key_review import (
    source_bound_schematic_erc_duplicate_severity_key_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.erc_duplicate_severity_key"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8@sha256:"
    "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
)
SCHEMATIC = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-duplicate-severity"
PROJECT_RELATIVE = "board.kicad_pro"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_ERC_DUPLICATE_SEVERITY_FIXTURES") != "1",
        reason="native schematic ERC duplicate-key fixtures run in the digest-pinned acceptance lane",
    ),
]


def _run_erc(
    tmp_path: Path,
    case: str,
    repeat: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    project = work / PROJECT_RELATIVE
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
        home_directory=f"schematic-erc-duplicate-{case}-{repeat}",
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
    severities = tuple(sorted(item["severity"] for item in violations))

    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=Path(PROJECT_RELATIVE),
            kicad_version=VERSION,
        ),
    )
    candidates = source_bound_schematic_erc_duplicate_severity_key_candidates(
        work,
        config,
        {PROJECT_RELATIVE: digest(project)},
    )
    values = tuple(
        value for candidate in candidates for value in candidate.evidence["configured_values_json"]
    )
    return severities, values


@pytest.mark.parametrize(
    ("case", "expected_severities", "expected_values"),
    (
        ("fault-ignore-last", (), ('"warning"', '"ignore"')),
        ("fault-warning-last", ("warning", "warning"), ('"ignore"', '"warning"')),
    ),
)
def test_kicad_1008_applies_last_duplicate_value_repeatably(
    tmp_path: Path,
    case: str,
    expected_severities: tuple[str, ...],
    expected_values: tuple[str, ...],
) -> None:
    runs = tuple(_run_erc(tmp_path, case, repeat) for repeat in ("first", "repeat"))

    assert all(severities == expected_severities for severities, _ in runs)
    assert all(values == expected_values for _, values in runs)
    assert runs[0] == runs[1]


def test_kicad_1008_honors_unique_warning_control_repeatably(tmp_path: Path) -> None:
    runs = tuple(_run_erc(tmp_path, "control-unique", repeat) for repeat in ("first", "repeat"))

    assert all(severities == ("warning", "warning") for severities, _ in runs)
    assert all(values == () for _, values in runs)
    assert runs[0] == runs[1]
