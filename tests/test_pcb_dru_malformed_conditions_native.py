"""Pinned native compilation behavior for malformed custom DRC conditions."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import CommandEvidence
from kicad_tooling.hwrepo.pcb_dru_compilation import (
    PcbDruCompilationReport,
    run_pcb_dru_compilation_probe,
)
from tests.native_kicad_support import execute_kicad_cli

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]
RULE_ID = "pcb.custom_drc_malformed_condition_clause"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
VERSION = "10.0.8"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-malformed-conditions"
PROJECT_FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint/control.kicad_pro"
)
PROBE_NAME = "pcb-dru-malformed-condition-probe"
CASES = {
    "control-single": ("control-single-condition.kicad_dru", "SingleCondition", True),
    "control-repeated": ("control-repeated-condition.kicad_dru", "RepeatedCondition", True),
    "control-empty-quoted": (
        "control-empty-quoted-expression.kicad_dru",
        "EmptyQuotedCondition",
        True,
    ),
    "fault-empty": ("fault-empty-expression.kicad_dru", "EmptyCondition", False),
    "fault-extra": ("fault-extra-condition-atom.kicad_dru", "ExtraConditionAtom", False),
}


def _run_probe(
    tmp_path: Path,
    case: str,
    fixture: str,
    repeat: str,
) -> tuple[PcbDruCompilationReport, tuple[str, ...]]:
    root = tmp_path / f"{case}-{repeat}"
    root.mkdir()
    project = root / f"{PROBE_NAME}.kicad_pro"
    rules = root / f"{PROBE_NAME}.kicad_dru"
    project.write_bytes(PROJECT_FIXTURE.read_bytes())
    rules.write_bytes((FIXTURES / fixture).read_bytes())
    output = root / "build/native"
    output.mkdir(parents=True)

    def executor(
        argv: tuple[str, ...], work: Path, command_output: Path, command_name: str
    ) -> CommandEvidence:
        command = execute_kicad_cli(
            IMAGE,
            argv,
            work,
            home_directory=f"pcb-dru-malformed-condition-{case}-{repeat}",
        )
        write_model(command_output / f"{command_name}.command.json", command)
        return command

    report = run_pcb_dru_compilation_probe(
        rules_path=rules,
        project_path=project,
        repository_root=root,
        output=output,
        cli="kicad-cli",
        expected_kicad_version=VERSION,
        image=IMAGE,
        execute=executor,
    )
    native_report = json.loads(
        (output / "drc-rule-compilation/probe-drc.json").read_text(encoding="utf-8")
    )
    violations = tuple(
        sorted(
            f"{item.get('type')}|{item.get('severity')}|{item.get('description')}"
            for item in native_report.get("violations", ())
        )
    )
    return report, violations


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_condition_shape_faults_suppress_native_rules_but_controls_match_repeatably(
    tmp_path: Path,
) -> None:
    for case, (fixture, rule_name, expected_to_compile) in CASES.items():
        first, first_violations = _run_probe(tmp_path, case, fixture, "first")
        repeat, repeated_violations = _run_probe(tmp_path, case, fixture, "repeat")

        assert first.observed_kicad_version == VERSION
        assert repeat.observed_kicad_version == VERSION
        assert first_violations == repeated_violations
        assert first.sentinel_matches == repeat.sentinel_matches
        if expected_to_compile:
            assert first.status == repeat.status == "PASS"
            assert first.sentinel_matches == 1
            widths = tuple(item for item in first_violations if item.startswith("track_width|"))
            assert len(widths) == 2
            assert all(f"rule '{rule_name}'" in item for item in widths)
        else:
            assert first.status == repeat.status == "FAIL"
            assert first.sentinel_matches == 0
            assert tuple(item.split("|", 1)[0] for item in first_violations) == (
                "track_dangling",
                "track_dangling",
            )
