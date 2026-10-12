"""Focused source-bound coverage for generic component power-input pins."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_component_power_input import GENERIC_COMPONENT_POWER_INPUT_CASES
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures.connector_power_cases import generic_component_power_input_cases
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def _lane_results(log: HostedLog) -> dict[str, dict[str, object]]:
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "component-power-input-fixture/"
    return {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}


def test_component_power_input_lane_exports_only_its_faults_and_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_power_input_fixture_lane import (
        component_power_input_fixture_lane,
    )

    root = tmp_path.resolve()
    image = PINNED_NATIVE_KICAD_IMAGES["10.0.0"]
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = generic_component_power_input_cases()

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == tmp_path.resolve()
        assert timeout == 600
        assert "--network" in argv
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert image in argv

        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in source_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in GENERIC_COMPONENT_POWER_INPUT_CASES
        }
        for case in GENERIC_COMPONENT_POWER_INPUT_CASES:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} netlist {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        case = path.name.split(".", 1)[0]
        return observed[case]

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)

    log = HostedLog(root, "component-power-input-unit")
    component_power_input_fixture_lane(root, project="synthetic", image=image, log=log)

    results = _lane_results(log)
    assert set(results) == {
        "component-power-input-fixture/native-export",
        *(f"component-power-input-fixture/{case}" for case in GENERIC_COMPONENT_POWER_INPUT_CASES),
    }
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    ):
        result = results[f"component-power-input-fixture/{case}"]
        assert result["lint_status"] == "REVIEW"
        assert result["findings"] == "component.unconnected_power_input"
        assert result["subjects"] == "U1.1: generic native power-input pin is unassigned"
    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        result = results[f"component-power-input-fixture/{case}"]
        assert result["lint_status"] == "PASS"
        assert result["findings"] == "none"


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_generic_component_power_input_cases_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_power_input_fixture_lane import (
        component_power_input_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-component-power-input-{project}")
    component_power_input_fixture_lane(root, project=project, image=config.image, log=log)
    results = _lane_results(log)
    assert set(results) == {
        "component-power-input-fixture/native-export",
        *(f"component-power-input-fixture/{case}" for case in GENERIC_COMPONENT_POWER_INPUT_CASES),
    }
    native_export = results["component-power-input-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == GENERIC_COMPONENT_POWER_INPUT_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    for case, expected_status, expected_findings in (
        (
            "unconnected-generic-component-power-input-fault",
            "REVIEW",
            "component.unconnected_power_input",
        ),
        (
            "unconnected-generic-component-power-input-no-connect-fault",
            "REVIEW",
            "component.unconnected_power_input",
        ),
        ("unconnected-generic-component-power-input-control", "PASS", "none"),
        ("unconnected-generic-component-power-input-dnp-control", "PASS", "none"),
    ):
        result = results[f"component-power-input-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == expected_status
        assert result["findings"] == expected_findings
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
