"""Pinned KiCad evidence for duplicated PCB object UUID diagnostics."""

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
from kicad_tooling.hwrepo.pcb_object_uuid_integrity import (
    duplicate_pcb_object_uuid_candidates,
)
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.duplicate_object_uuid"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-duplicate-object-uuid"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _native_uuid_report(tmp_path: Path, version: str, case: str, repeat: str) -> dict:
    work = tmp_path / f"{version}-{case}-{repeat}"
    work.mkdir()
    output = work / "output"
    output.mkdir()
    report_path = output / "drc.json"
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    command = execute_kicad_cli(
        image,
        (
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            str(report_path),
            str(FIXTURES / f"{case}.kicad_pcb"),
        ),
        work,
        home_directory=f"pcb-duplicate-uuid-{version}-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == version
    violation_types = {str(item.get("type", "")).casefold() for item in report["violations"]}
    assert not any("duplicate" in value and "uuid" in value for value in violation_types)

    source_root = work / "source"
    board_relative = "projects/synthetic/controller.kicad_pcb"
    board_path = source_root / board_relative
    board_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="projects/synthetic/controller.kicad_pro",
            kicad_version=version,
        ),
    )
    candidates = duplicate_pcb_object_uuid_candidates(
        source_root,
        config,
        {board_relative: digest(board_path)},
    )
    assert tuple(candidate.rule_id for candidate in candidates) == (
        (RULE_ID,) if case == "fault" else ()
    )
    return report


def _track_and_unconnected_uuids(report: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    dangling = tuple(
        sorted(
            item["uuid"]
            for violation in report["violations"]
            if violation.get("type") == "track_dangling"
            for item in violation.get("items", ())
        )
    )
    unconnected = tuple(
        sorted(
            item["uuid"] for issue in report["unconnected_items"] for item in issue.get("items", ())
        )
    )
    return dangling, unconnected


def test_pinned_kicad_drc_reuses_duplicate_segment_uuid(tmp_path: Path) -> None:
    for version in ("10.0.0", "10.0.5"):
        reports = {
            case: tuple(
                _track_and_unconnected_uuids(_native_uuid_report(tmp_path, version, case, repeat))
                for repeat in ("a", "b")
            )
            for case in ("fault", "control")
        }
        repeated_uuid = "00000000-0000-0000-0000-000000000002"
        other_uuid = "00000000-0000-0000-0000-000000000003"
        expected_fault = ((repeated_uuid, repeated_uuid), (repeated_uuid, repeated_uuid))
        expected_control = (
            tuple(sorted((repeated_uuid, other_uuid))),
            tuple(sorted((repeated_uuid, other_uuid))),
        )
        assert reports["fault"] == (expected_fault, expected_fault)
        assert reports["control"] == (expected_control, expected_control)
