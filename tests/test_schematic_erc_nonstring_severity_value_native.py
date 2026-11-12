"""Pinned KiCad proof for non-string schematic ERC severity values."""

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
from kicad_tooling.hwrepo.schematic_erc_nonstring_severity_value_review import (
    source_bound_schematic_erc_nonstring_severity_value_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id="schematic.erc_nonstring_severity_value"),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_ERC_NONSTRING_SEVERITY_FIXTURES") != "1",
        reason="native schematic ERC non-string fixtures run in the digest-pinned acceptance lane",
    ),
]

RULE_ID = "schematic.erc_nonstring_severity_value"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8@sha256:"
    "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
)
SCHEMATIC = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-nonstring-severity"
PROJECT_RELATIVE = "board.kicad_pro"


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
        home_directory=f"schematic-erc-nonstring-{case}-{repeat}",
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
    assert len(severities) == 2

    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=Path(PROJECT_RELATIVE),
            kicad_version=VERSION,
        ),
    )
    candidates = source_bound_schematic_erc_nonstring_severity_value_candidates(
        work,
        config,
        {PROJECT_RELATIVE: digest(project)},
    )
    values = tuple(item.evidence["configured_value_json"][0] for item in candidates)
    return severities, values


@pytest.mark.parametrize(
    ("case", "expected_value"),
    (
        ("fault-boolean", "true"),
        ("fault-number", "7"),
        ("fault-null", "null"),
        ("fault-array", "[]"),
        ("fault-object", '{"mode":"warning"}'),
    ),
)
def test_kicad_1008_keeps_nonstring_severity_at_error(
    tmp_path: Path,
    case: str,
    expected_value: str,
) -> None:
    fault = tuple(_run_erc(tmp_path, case, repeat) for repeat in ("first", "repeat"))

    assert all(severities == ("error", "error") for severities, _ in fault)
    assert all(values == (expected_value,) for _, values in fault)
    assert fault[0][0] == fault[1][0]


def test_kicad_1008_honors_valid_warning_control_repeatably(tmp_path: Path) -> None:
    control = tuple(_run_erc(tmp_path, "control", repeat) for repeat in ("first", "repeat"))

    assert all(severities == ("warning", "warning") for severities, _ in control)
    assert all(values == () for _, values in control)
    assert control[0][0] == control[1][0]
