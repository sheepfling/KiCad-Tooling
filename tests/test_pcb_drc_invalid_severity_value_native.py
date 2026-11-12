"""Pinned KiCad proof that malformed DRC severity strings become Error."""

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
from kicad_tooling.hwrepo.pcb_drc_invalid_severity_value_review import (
    source_bound_pcb_drc_invalid_severity_value_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import (
    NativePcbDrcFixtureReport,
    read_native_pcb_drc_fixture_report,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]

RULE_ID = "pcb.drc_invalid_severity_value"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
BOARD = Path(__file__).parent / "fixtures/design_lint/pcb-reference-zone-island/fault.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-invalid-severity-value"
PROJECT = "board.kicad_pro"


def _run_drc(
    tmp_path: Path, case: str, repeat: str
) -> tuple[NativePcbDrcFixtureReport, tuple[str, ...]]:
    work = tmp_path / f"{case}-{repeat}"
    work.mkdir()
    board = work / "board.kicad_pcb"
    project = work / PROJECT
    shutil.copyfile(BOARD, board)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pro", project)
    report_path = work / "drc.json"
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
            str(report_path),
            str(board),
        ),
        work,
        home_directory=f"pcb-drc-invalid-severity-{case}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = read_native_pcb_drc_fixture_report(report_path)
    assert report.kicad_version == VERSION
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    dangling_severities = tuple(
        item["severity"] for item in payload["violations"] if item.get("type") == "track_dangling"
    )

    if case == "fault":
        config = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=VERSION),
        )
        candidates = source_bound_pcb_drc_invalid_severity_value_candidates(
            work,
            config,
            {PROJECT: digest(project)},
        )
        assert RULE_ID in {item.rule_id for item in candidates}
        assert '"warnnig"' in {item.evidence["configured_value_json"][0] for item in candidates}

    return report, dangling_severities


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_kicad_1008_maps_invalid_string_to_error_and_honors_warning_control_repeatably(
    tmp_path: Path,
) -> None:
    fault = tuple(_run_drc(tmp_path, "fault", repeat) for repeat in ("a", "b"))
    control = tuple(_run_drc(tmp_path, "control", repeat) for repeat in ("a", "b"))

    assert all("track_dangling" in item[0].violation_types for item in (*fault, *control))
    assert all(set(item[1]) == {"error"} for item in fault)
    assert all(set(item[1]) == {"warning"} for item in control)
    assert fault[0][1] == fault[1][1]
    assert control[0][1] == control[1][1]
