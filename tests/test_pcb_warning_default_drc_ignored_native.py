"""Pinned KiCad proof that an ignored warning-default check is suppressed."""

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
from kicad_tooling.hwrepo.pcb_drc_global_severity_review import (
    ignored_warning_default_native_drc_check_candidates,
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

RULE_ID = "pcb.warning_default_drc_check_ignored"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
BOARD = Path(__file__).parent / "fixtures/design_lint/pcb-reference-zone-island/fault.kicad_pcb"
PROJECT = "board.kicad_pro"


def _run_drc(
    tmp_path: Path, severity: str, repeat: str
) -> tuple[NativePcbDrcFixtureReport, tuple[str, ...]]:
    work = tmp_path / f"{severity}-{repeat}"
    work.mkdir()
    board = work / "board.kicad_pcb"
    project = work / PROJECT
    shutil.copyfile(BOARD, board)
    project.write_text(
        json.dumps(
            {
                "board": {"design_settings": {"rule_severities": {"track_dangling": severity}}},
                "meta": {"filename": PROJECT, "version": 1},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
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
        home_directory=f"pcb-warning-default-{severity}-{repeat}",
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = read_native_pcb_drc_fixture_report(report_path)
    assert report.kicad_version == VERSION
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    track_dangling_records = tuple(
        json.dumps(item, sort_keys=True)
        for item in payload["violations"]
        if item.get("type") == "track_dangling"
    )

    if severity == "ignore":
        config = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT, kicad_version=VERSION),
        )
        candidates = ignored_warning_default_native_drc_check_candidates(
            work, config, {PROJECT: digest(project)}
        )
        assert RULE_ID in {item.rule_id for item in candidates}
        assert "track_dangling" in {item.evidence["check_id"][0] for item in candidates}

    return report, track_dangling_records


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_kicad_1008_suppresses_ignored_warning_default_check_repeatably(
    tmp_path: Path,
) -> None:
    warning = tuple(_run_drc(tmp_path, "warning", repeat) for repeat in ("a", "b"))
    ignored = tuple(_run_drc(tmp_path, "ignore", repeat) for repeat in ("a", "b"))

    assert warning[0][0].violation_types.count("track_dangling") == 1
    assert "track_dangling" in warning[1][0].violation_types
    assert "track_dangling" not in ignored[0][0].violation_types
    assert "track_dangling" not in ignored[1][0].violation_types
    assert warning[0][1] == warning[1][1]
    assert ignored[0][1] == ignored[1][1] == ()
