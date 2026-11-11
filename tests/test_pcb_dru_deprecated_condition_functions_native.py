"""Check deprecated and replacement condition syntax on pinned KiCad 10.0.8."""

from __future__ import annotations

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
RULE_ID = "pcb.custom_drc_deprecated_condition_function"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8-amd64@sha256:"
    "05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c"
)
VERSION = "10.0.8"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-deprecated-condition-functions"
PROJECT_FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint/control.kicad_pro"
)
PROBE_NAME = "pcb-dru-deprecated-function-probe"


def _run_probe(tmp_path: Path, name: str, fixture: str) -> PcbDruCompilationReport:
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
        command = execute_kicad_cli(IMAGE, argv, work, home_directory=f"dru-deprecated-{name}")
        write_model(command_output / f"{command_name}.command.json", command)
        return command

    return run_pcb_dru_compilation_probe(
        rules_path=rules,
        project_path=project,
        repository_root=root,
        output=output,
        cli="kicad-cli",
        expected_kicad_version=VERSION,
        image=IMAGE,
        execute=executor,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_deprecated_and_replacement_calls_reach_native_sentinel_on_kicad_1008(
    tmp_path: Path,
) -> None:
    fault = _run_probe(tmp_path, "deprecated", "fault.kicad_dru")
    control = _run_probe(tmp_path, "replacement", "control.kicad_dru")
    fault_repeat = _run_probe(tmp_path, "deprecated-repeat", "fault.kicad_dru")
    control_repeat = _run_probe(tmp_path, "replacement-repeat", "control.kicad_dru")

    for report in (fault, control, fault_repeat, control_repeat):
        assert report.status == "PASS", report.issue
        assert report.observed_kicad_version == VERSION
        assert report.sentinel_matches >= 1
    assert (
        fault.status,
        fault.observed_kicad_version,
        fault.native_returncode,
        fault.sentinel_matches,
    ) == (
        fault_repeat.status,
        fault_repeat.observed_kicad_version,
        fault_repeat.native_returncode,
        fault_repeat.sentinel_matches,
    )
    assert (
        control.status,
        control.observed_kicad_version,
        control.native_returncode,
        control.sentinel_matches,
    ) == (
        control_repeat.status,
        control_repeat.observed_kicad_version,
        control_repeat.native_returncode,
        control_repeat.sentinel_matches,
    )
