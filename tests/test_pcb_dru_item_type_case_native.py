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
OBJECT_TYPE_EXPECTED_HOLE_MATCHES = {
    "10.0.0": {"SyntheticViaHoleSize": 0, "SyntheticPadHoleSize": 1},
    "10.0.5": {"SyntheticViaHoleSize": 1, "SyntheticPadHoleSize": 1},
    "10.0.8": {"SyntheticViaHoleSize": 1, "SyntheticPadHoleSize": 1},
}


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


@pytest.mark.parametrize(("kicad_version", "image"), KICAD_10_PCB_TYPE_CASE_TOOLCHAINS)
def test_native_via_and_pad_type_case_variants_have_equal_behavior(
    tmp_path: Path,
    kicad_version: str,
    image: str,
) -> None:
    root = tmp_path / "synthetic-object-type-project"
    root.mkdir()
    board_name = "pcb-dru-object-type-case-probe"
    board = root / f"{board_name}.kicad_pcb"
    board.write_bytes((FIXTURES / "object-types.kicad_pcb").read_bytes())
    project = root / f"{board_name}.kicad_pro"
    project.write_bytes((FIXTURES / "object-types.kicad_pro").read_bytes())
    sentinel_name = "KTT_ITEM_TYPE_CASE_SENTINEL"

    def run_case(source_fixture: str, case: str, repeat: str) -> tuple[int, dict[str, int]]:
        rules = root / f"{board_name}.kicad_dru"
        rules.write_bytes((FIXTURES / source_fixture).read_bytes())
        output = root / "build/native" / f"{case}-{repeat}"
        output.mkdir(parents=True)
        report_path = output / "drc.json"
        command = execute_kicad_cli(
            image,
            (
                "kicad-cli",
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--exit-code-violations",
                "--output",
                str(report_path),
                str(board),
            ),
            root,
            home_directory=f"dru-type-object-{kicad_version}-{case}-{repeat}",
        )
        write_model(output / "native-command.json", command)
        assert command.error is None
        assert command.returncode == 5
        assert report_path.is_file()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["kicad_version"] == kicad_version
        violations = report["violations"]
        descriptions = tuple(
            str(item.get("description", "")) for item in violations if isinstance(item, dict)
        )
        counts = {
            name: sum(
                1
                for item in violations
                if isinstance(item, dict)
                and item.get("type") == "drill_out_of_range"
                and name in str(item.get("description", ""))
            )
            for name in ("SyntheticViaHoleSize", "SyntheticPadHoleSize")
        }
        assert any(sentinel_name in description for description in descriptions)
        return command.returncode, counts

    results = {
        case: tuple(run_case(source_fixture, case, repeat) for repeat in ("first", "repeat"))
        for case, source_fixture in (
            ("lowercase", "fault-lowercase-object-types.kicad_dru"),
            ("canonical", "control-canonical-object-types.kicad_dru"),
        )
    }
    for first, repeat in results.values():
        assert first == repeat

    lowercase_returncode, lowercase_matches = results["lowercase"][0]
    canonical_returncode, canonical_matches = results["canonical"][0]
    assert lowercase_returncode == canonical_returncode == 5
    assert (
        lowercase_matches == canonical_matches == OBJECT_TYPE_EXPECTED_HOLE_MATCHES[kicad_version]
    )
