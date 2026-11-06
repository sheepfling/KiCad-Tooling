"""Exact-version native behavior for conflicting custom DRC severities."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.pcb_dru_compilation import run_pcb_dru_compilation_probe
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.pcb_lint,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]
RULE_ID = "pcb.custom_drc_conflicting_severities"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-conflicting-severities"
PROJECT = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-without-constraint/control.kicad_pro"
)
EXPECTED_AUTHORED_SEVERITIES = {
    "10.0.0": {"multiple": (), "single": ()},
    "10.0.5": {"multiple": ("warning", "warning"), "single": ("error", "error")},
}
EXPECTED_SOURCE_HASHES = {
    "fault-multiple-severities.kicad_dru": "e682b07006dcb97a231012cbf396535018b3d4b5754c0d272d7e735a01db2ba2",
    "control-one-severity.kicad_dru": "8e75fa7d5483d38a641d0c888fb85fcc2d83f77c91f2dbee2486d1948e4b67fc",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(("kicad_version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_multiple_and_single_severity_rules_reach_native_sentinel(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    root = tmp_path / "synthetic-native-project"
    root.mkdir()
    project = root / "synthetic.kicad_pro"
    project.write_bytes(PROJECT.read_bytes())
    observations: dict[str, tuple[str, ...]] = {}

    for case, fixture in (
        ("multiple", "fault-multiple-severities.kicad_dru"),
        ("single", "control-one-severity.kicad_dru"),
    ):
        rules = root / "synthetic.kicad_dru"
        rules.write_bytes((FIXTURES / fixture).read_bytes())
        repeated: list[tuple[str, ...]] = []
        for repetition in ("first", "repeat"):
            output = tmp_path / "build/native" / case / repetition
            output.mkdir(parents=True)

            def executor(
                argv: Sequence[str],
                work: Path,
                command_output: Path,
                command_name: str,
                *,
                case: str = case,
                repetition: str = repetition,
            ) -> CommandEvidence:
                command = execute_kicad_cli(
                    image,
                    tuple(argv),
                    work,
                    home_directory=f"dru-conflicting-severity-{case}-{repetition}-{kicad_version}",
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
            assert report.rules_sha256 == EXPECTED_SOURCE_HASHES[fixture]
            assert report.status == "PASS", report.model_dump_json(indent=2)
            assert report.observed_kicad_version == kicad_version
            assert report.sentinel_matches >= 1
            native = json.loads(
                (output / "drc-rule-compilation/probe-drc.json").read_text(encoding="utf-8")
            )
            matches = tuple(
                sorted(
                    str(item.get("severity"))
                    for item in native["violations"]
                    if isinstance(item, dict)
                    and item.get("type") == "track_width"
                    and "SyntheticTrackWidth" in str(item.get("description", ""))
                )
            )
            repeated.append(matches)
        assert repeated[0] == repeated[1]
        observations[case] = repeated[0]

    assert observations == EXPECTED_AUTHORED_SEVERITIES[kicad_version]
