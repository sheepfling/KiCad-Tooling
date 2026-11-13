"""Pinned native DRC evidence for duplicate same-number pad assignments."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_duplicate_pad_net_conflicts import (
    duplicate_pad_net_conflict_candidates,
)
from tests.design_lint_fixtures.pcb_component_inventory import netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "pcb.duplicate_pad_net_conflict"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-duplicate-pad-net-conflict"
BOARD = "projects/synthetic/controller.kicad_pcb"
PROJECT = "projects/synthetic/controller.kicad_pro"
SOURCE_SHA256 = {
    "fault.kicad_pcb": "a5e967fdf823d1f8378c15a0120879597b2806bccbf69ab798efdf5e47a210fe",
    "control.kicad_pcb": "5690052e7ef96d3980111092a2c983c4d6b944a510bacb9627ea7f389e422246",
}

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


def _native_report(tmp_path: Path, version: str, case: str, run: str) -> dict:
    work = tmp_path / f"{version}-{case}-{run}"
    output = work / "output"
    output.mkdir(parents=True)
    report_path = output / "drc.json"
    command = execute_kicad_cli(
        PINNED_NATIVE_KICAD_IMAGES[version],
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
        home_directory=f"duplicate-pad-net-conflict-{version}-{case}-{run}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kicad_version"] == version
    return report


def _candidate_ids(tmp_path: Path, version: str, case: str) -> tuple[str, ...]:
    root = tmp_path / f"candidate-{version}-{case}"
    board_path = root / BOARD
    board_path.parent.mkdir(parents=True)
    source = FIXTURES / f"{case}.kicad_pcb"
    board_path.write_bytes(source.read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT, kicad_version=version),
    )
    observed = netlist(
        components={"J1": "Synthetic:TwoPadConnector"},
        nets={"SIGNAL": ("J1.1",)},
        component_pin_numbers={"J1": ("1",)},
    )
    candidates = duplicate_pad_net_conflict_candidates(
        root,
        config,
        {BOARD: digest(board_path)},
        observed,
    )
    return tuple(candidate.rule_id for candidate in candidates)


def _native_semantics(report: dict) -> str:
    return json.dumps(
        {
            "violations": report["violations"],
            "unconnected_items": report["unconnected_items"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_native_drc_does_not_distinguish_duplicate_pad_net_conflict(
    tmp_path: Path,
) -> None:
    for version in tuple(PINNED_NATIVE_KICAD_IMAGES):
        reports = {}
        for case in ("fault", "control"):
            source = FIXTURES / f"{case}.kicad_pcb"
            assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256[source.name]
            assert _candidate_ids(tmp_path, version, case) == (
                (RULE_ID,) if case == "fault" else ()
            )
            repeated = tuple(
                _native_report(tmp_path, version, case, run) for run in ("first", "repeat")
            )
            assert _native_semantics(repeated[0]) == _native_semantics(repeated[1])
            reports[case] = repeated[0]

        fault = reports["fault"]
        control = reports["control"]
        assert fault["unconnected_items"] == control["unconnected_items"] == []
        assert [item["type"] for item in fault["violations"]] == ["lib_footprint_issues"]
        assert _native_semantics(fault) == _native_semantics(control)
