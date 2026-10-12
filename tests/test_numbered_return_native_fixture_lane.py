"""Focused source-bound coverage for numbered connector return labels."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures.connector_return_cases import pwm_return_case_contracts
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]

_PWM_CASES = tuple(pwm_return_case_contracts())


def test_numbered_pwm_lane_exports_only_its_fault_and_control_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_connector_return_lane import numbered_pwm_return_fixture_lane

    root = tmp_path.resolve()
    image = PINNED_NATIVE_KICAD_IMAGES["10.0.0"]
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = pwm_return_case_contracts()

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
            f"{case}.kicad_sch" for case in _PWM_CASES
        }
        for case in _PWM_CASES:
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

    log = HostedLog(root, "numbered-pwm-return-unit")
    numbered_pwm_return_fixture_lane(root, project="synthetic", image=image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("connector-return-fixture/")
    }
    assert set(results) == {
        "connector-return-fixture/native-export",
        *(f"connector-return-fixture/{case}" for case in _PWM_CASES),
    }
    assert results["connector-return-fixture/four-db9-pwm-fault"]["lint_status"] == "REVIEW"
    assert set(results["connector-return-fixture/four-db9-pwm-fault"]["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert results["connector-return-fixture/four-db9-pwm-control"]["lint_status"] == "PASS"
    assert results["connector-return-fixture/four-db9-pwm-control"]["findings"] == "none"


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="native connector fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_numbered_pwm_return_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_connector_return_lane import numbered_pwm_return_fixture_lane
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

    log = HostedLog(root, f"native-numbered-pwm-return-{project}")
    numbered_pwm_return_fixture_lane(root, project=project, image=config.image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("connector-return-fixture/")
    }
    assert set(results) == {
        "connector-return-fixture/native-export",
        *(f"connector-return-fixture/{case}" for case in _PWM_CASES),
    }
    native_export = results["connector-return-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == _PWM_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results["connector-return-fixture/four-db9-pwm-fault"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert set(fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert fault["kicad_version"] == version
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]

    control = results["connector-return-fixture/four-db9-pwm-control"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert control["kicad_version"] == version
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
