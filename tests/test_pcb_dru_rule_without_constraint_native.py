"""Exact-version KiCad compilation evidence for unconstrained custom rules."""

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
RULE_ID = "pcb.custom_drc_rule_without_constraint"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint"
PROBE_NAME = "pcb-dru-rule-compilation-probe"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_unconstrained_rule_does_not_prevent_terminal_sentinel(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    root = tmp_path / "synthetic-native-project"
    root.mkdir()
    project = root / f"{PROBE_NAME}.kicad_pro"
    project.write_bytes((FIXTURES / "control.kicad_pro").read_bytes())

    def run_probe(name: str, source_fixture: str) -> PcbDruCompilationReport:
        rules = root / f"{PROBE_NAME}.kicad_dru"
        rules.write_bytes((FIXTURES / source_fixture).read_bytes())
        output = root / "build/native" / name
        output.mkdir(parents=True)

        def executor(
            argv: tuple[str, ...], work: Path, command_output: Path, command_name: str
        ) -> CommandEvidence:
            command = execute_kicad_cli(
                image,
                argv,
                work,
                home_directory=f"dru-no-constraint-{name}",
            )
            write_model(command_output / f"{command_name}.command.json", command)
            return command

        return run_pcb_dru_compilation_probe(
            rules_path=rules,
            project_path=project,
            repository_root=root,
            output=output,
            cli="kicad-cli",
            expected_kicad_version=kicad_version,
            image=image,
            execute=executor,
        )

    fault = run_probe("unconstrained", "fault-no-constraint.kicad_dru")
    control = run_probe("constrained", "control-active.kicad_dru")

    assert fault.status == control.status == "PASS"
    assert fault.observed_kicad_version == control.observed_kicad_version == kicad_version
    assert fault.sentinel_matches >= 1
    assert control.sentinel_matches >= 1
    assert fault.native_returncode == control.native_returncode == 5
