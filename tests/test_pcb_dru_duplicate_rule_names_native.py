"""Exact-version KiCad sentinel checks for duplicate custom DRC rule names."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.pcb_dru_compilation import (
    PcbDruCompilationReport,
    run_pcb_dru_compilation_probe,
)
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

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
RULE_ID = "pcb.custom_drc_duplicate_rule_name"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-duplicate-rule-name"
PROJECT_FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint/control.kicad_pro"
)
EXPECTED_RULE_SOURCE_HASHES = {
    "fault-duplicate-names.kicad_dru": "ab8c380983998f61697cc105a8b3d0945994546158a96d8e085088fbb8074161",
    "control-unique-names.kicad_dru": "9a3bd4a9d0672fd22f107873121f0e6a134a31f35e088f4c5d4e36e6f03b7ebf",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_duplicate_and_unique_rule_names_reach_native_sentinel(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    root = tmp_path / "synthetic-native-project"
    root.mkdir()
    project = root / "synthetic.kicad_pro"
    project.write_bytes(PROJECT_FIXTURE.read_bytes())

    def run_probe(case: str, source_fixture: str, repetition: str) -> PcbDruCompilationReport:
        rules = root / "synthetic.kicad_dru"
        rules.write_bytes((FIXTURES / source_fixture).read_bytes())
        output = tmp_path / "build/native" / case / repetition
        output.mkdir(parents=True)

        def executor(
            argv: Sequence[str], work: Path, command_output: Path, command_name: str
        ) -> CommandEvidence:
            command = execute_kicad_cli(
                image,
                tuple(argv),
                work,
                home_directory=f"dru-duplicate-name-{case}-{repetition}-{kicad_version}",
            )
            write_model(command_output / f"{command_name}.command.json", command)
            return command

        report = run_pcb_dru_compilation_probe(
            rules_path=rules,
            project_path=project,
            repository_root=root,
            output=output,
            cli="kicad-cli",
            expected_kicad_version=kicad_version,
            image=image,
            execute=executor,
        )
        assert report.rules_sha256 == EXPECTED_RULE_SOURCE_HASHES[source_fixture]
        return report

    fault_runs = tuple(
        run_probe("duplicate-names", "fault-duplicate-names.kicad_dru", repetition)
        for repetition in ("first", "repeat")
    )
    control_runs = tuple(
        run_probe("unique-names", "control-unique-names.kicad_dru", repetition)
        for repetition in ("first", "repeat")
    )

    for report in (*fault_runs, *control_runs):
        assert report.status == "PASS"
        assert report.observed_kicad_version == kicad_version
        assert report.sentinel_matches >= 1
    for first, repeat in (fault_runs, control_runs):
        assert first.rules_sha256 == repeat.rules_sha256
        assert first.sentinel_rule_name == repeat.sentinel_rule_name
        assert first.sentinel_matches == repeat.sentinel_matches
