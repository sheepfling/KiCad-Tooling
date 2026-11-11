"""Pinned native trials for custom DRC layer references."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import CommandEvidence
from kicad_tooling.hwrepo.pcb_drc_rule_parser import read_native_pcb_drc_fixture_report
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
RULE_ID = "pcb.custom_drc_layer_reference"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
VERSION = "10.0.8"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-layer-reference"
PROJECT_FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint/control.kicad_pro"
)
PROBE_NAME = "pcb-dru-rule-compilation-probe"


def _run_probe(tmp_path: Path, name: str, fixture: str) -> tuple[PcbDruCompilationReport, Path]:
    root = tmp_path / name
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
        command = execute_kicad_cli(IMAGE, argv, work, home_directory=f"dru-layer-{name}")
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
    return report, output / "drc-rule-compilation/probe-drc.json"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_layer_name_faults_and_controls_on_pinned_kicad_1008(tmp_path: Path) -> None:
    alias, alias_report_path = _run_probe(
        tmp_path, "display-alias", "fault-display-alias.kicad_dru"
    )
    unknown, unknown_report_path = _run_probe(
        tmp_path, "unknown-layer", "fault-unknown-layer.kicad_dru"
    )
    absent, absent_report_path = _run_probe(
        tmp_path, "absent-layer", "fault-absent-stackup-layer.kicad_dru"
    )
    control, control_report_path = _run_probe(
        tmp_path, "canonical-control", "control-canonical-layers.kicad_dru"
    )
    repeats = {
        "display-alias": _run_probe(
            tmp_path, "display-alias-repeat", "fault-display-alias.kicad_dru"
        ),
        "unknown-layer": _run_probe(
            tmp_path, "unknown-layer-repeat", "fault-unknown-layer.kicad_dru"
        ),
        "absent-layer": _run_probe(
            tmp_path, "absent-layer-repeat", "fault-absent-stackup-layer.kicad_dru"
        ),
        "canonical-control": _run_probe(
            tmp_path, "canonical-control-repeat", "control-canonical-layers.kicad_dru"
        ),
    }

    assert alias.status == "PASS" and alias.sentinel_matches >= 1
    assert alias.observed_kicad_version == VERSION
    assert unknown.status == "FAIL" and unknown.sentinel_matches == 0
    assert unknown.native_returncode == 5
    assert unknown.issue is not None and "terminal sentinel" in unknown.issue
    assert absent.status == "PASS" and absent.sentinel_matches >= 1
    assert absent.observed_kicad_version == VERSION
    assert control.status == "PASS" and control.sentinel_matches >= 1
    assert control.observed_kicad_version == VERSION

    absent_report = read_native_pcb_drc_fixture_report(absent_report_path)
    control_report = read_native_pcb_drc_fixture_report(control_report_path)
    assert absent_report.kicad_version == control_report.kicad_version == VERSION
    assert "track_width" not in absent_report.violation_types
    assert "track_width" in control_report.violation_types

    first_runs = {
        "display-alias": (alias, alias_report_path),
        "unknown-layer": (unknown, unknown_report_path),
        "absent-layer": (absent, absent_report_path),
        "canonical-control": (control, control_report_path),
    }
    for name, (repeat, report_path) in repeats.items():
        first, first_path = first_runs[name]
        report = read_native_pcb_drc_fixture_report(report_path)
        first_types = read_native_pcb_drc_fixture_report(first_path).violation_types
        assert (
            repeat.status,
            repeat.observed_kicad_version,
            repeat.native_returncode,
            repeat.sentinel_matches,
            report.violation_types,
        ) == (
            first.status,
            first.observed_kicad_version,
            first.native_returncode,
            first.sentinel_matches,
            first_types,
        )
