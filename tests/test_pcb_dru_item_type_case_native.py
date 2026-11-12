"""Negative cohort trial for custom DRC item-type literal case sensitivity."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_ERC_SEVERITY_TOOLCHAINS
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
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-item-type-case"
PROBE_NAME = "pcb-dru-rule-compilation-probe"
KICAD_10_PCB_TYPE_CASE_TOOLCHAINS = tuple(
    (version, image)
    for version, image in KICAD_10_ERC_SEVERITY_TOOLCHAINS
    if version in {"10.0.0", "10.0.5", "10.0.8"}
)
EXPECTED_AUTHORED_TRACK_WIDTH_MATCHES = {"10.0.0": 0, "10.0.5": 2, "10.0.8": 2}


@pytest.mark.parametrize(("kicad_version", "image"), KICAD_10_PCB_TYPE_CASE_TOOLCHAINS)
def test_native_case_variants_have_equal_behavior_on_pinned_versions(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    root = tmp_path / "synthetic-native-project"
    root.mkdir()
    project = root / f"{PROBE_NAME}.kicad_pro"
    project.write_bytes((FIXTURES / "control.kicad_pro").read_bytes())

    def run_case(
        name: str, source_fixture: str, repeat: str
    ) -> tuple[PcbDruCompilationReport, int]:
        rules = root / f"{PROBE_NAME}.kicad_dru"
        rules.write_bytes((FIXTURES / source_fixture).read_bytes())
        output = root / "build/native" / f"{name}-{repeat}"
        output.mkdir(parents=True)

        def executor(
            argv: tuple[str, ...], work: Path, command_output: Path, command_name: str
        ) -> CommandEvidence:
            command = execute_kicad_cli(
                image,
                argv,
                work,
                home_directory=f"dru-type-case-{kicad_version}-{name}-{repeat}",
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
        assert report.status == "PASS", report.model_dump_json(indent=2)
        assert report.observed_kicad_version == kicad_version
        assert report.sentinel_matches >= 1
        native_report = json.loads(
            (output / "drc-rule-compilation/probe-drc.json").read_text(encoding="utf-8")
        )
        violations = native_report["violations"]
        authored_rule_matches = sum(
            1
            for violation in violations
            if isinstance(violation, dict)
            and violation.get("type") == "track_width"
            and isinstance(violation.get("description"), str)
            and "SyntheticTrackWidth" in violation["description"]
        )
        return report, authored_rule_matches

    results = {
        name: tuple(run_case(name, rule_file, repeat) for repeat in ("first", "repeat"))
        for name, rule_file in (
            ("lowercase", "fault-lowercase.kicad_dru"),
            ("canonical", "control-canonical.kicad_dru"),
        )
    }
    for (first, first_matches), (repeat, repeat_matches) in results.values():
        assert first.native_returncode == repeat.native_returncode == 5
        assert first.status == repeat.status == "PASS"
        assert first.observed_kicad_version == repeat.observed_kicad_version == kicad_version
        assert first.sentinel_matches == repeat.sentinel_matches >= 1
        assert first_matches == repeat_matches

    lowercase, lowercase_matches = results["lowercase"][0]
    canonical, canonical_matches = results["canonical"][0]
    assert lowercase.native_returncode == canonical.native_returncode == 5
    assert lowercase_matches == canonical_matches
    assert lowercase_matches == EXPECTED_AUTHORED_TRACK_WIDTH_MATCHES[kicad_version]
