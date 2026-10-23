"""Exact-version KiCad acceptance for custom DRC rule-file compilation proof."""

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
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.pcb_lint,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-compilation"


def _failure_context(report: PcbDruCompilationReport, output: Path) -> str:
    command_path = output / "drc-rule-compilation/native-command.command.json"
    command = command_path.read_text(encoding="utf-8") if command_path.is_file() else "missing"
    native_report_path = output / "drc-rule-compilation/probe-drc.json"
    native_report = (
        native_report_path.read_text(encoding="utf-8")
        if native_report_path.is_file()
        else "missing"
    )
    return (
        f"probe report:\n{report.model_dump_json(indent=2)}\n"
        f"native command evidence:\n{command}\n"
        f"native DRC report:\n{native_report}"
    )


@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_drc_proves_terminal_rule_and_rejects_malformed_custom_rules(
    tmp_path: Path, kicad_version: str, image: str
) -> None:
    root = tmp_path / "synthetic-project"
    root.mkdir()
    project = root / "board.kicad_pro"
    rules = root / "board.kicad_dru"
    output = root / "build/native"
    output.mkdir(parents=True)

    def executor(
        argv: tuple[str, ...], work: Path, command_output: Path, name: str
    ) -> CommandEvidence:
        command = execute_kicad_cli(
            image,
            argv,
            work,
            home_directory="kicad-dru-rule-probe",
        )
        write_model(command_output / f"{name}.command.json", command)
        return command

    project.write_bytes((FIXTURES / "control.kicad_pro").read_bytes())
    rules.write_bytes((FIXTURES / "control.kicad_dru").read_bytes())
    control = run_pcb_dru_compilation_probe(
        rules_path=rules,
        project_path=project,
        repository_root=root,
        output=output / "control",
        cli="kicad-cli",
        expected_kicad_version=kicad_version,
        image=image,
        execute=executor,
    )
    assert control.status == "PASS", _failure_context(control, output / "control")
    assert control.observed_kicad_version == kicad_version
    assert control.sentinel_matches >= 1
    assert control.native_returncode == 5

    rules.write_bytes((FIXTURES / "fault-malformed-syntax.kicad_dru").read_bytes())
    fault = run_pcb_dru_compilation_probe(
        rules_path=rules,
        project_path=project,
        repository_root=root,
        output=output / "fault",
        cli="kicad-cli",
        expected_kicad_version=kicad_version,
        image=image,
        execute=executor,
    )
    assert fault.status == "FAIL", _failure_context(fault, output / "fault")
    assert fault.sentinel_matches == 0
    assert fault.issue
