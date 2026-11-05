"""Synthetic orchestration and exact-version acceptance for GPIO control voltage lint."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted_gpio_control_voltage as lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence
from tests.design_lint_fixtures.gpio_control_voltage import gpio_control_voltage_netlist
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.power_lint]

PROJECT_TOOLCHAINS = (
    pytest.param(
        "controller",
        "10.0.0",
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        id="controller-kicad-10.0.0",
    ),
    pytest.param(
        "raspberry-pi-status-led",
        "10.0.5",
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        id="raspberry-pi-status-led-kicad-10.0.5",
    ),
)


@pytest.fixture
def native_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    return root


def _stage_results(log: HostedLog) -> dict[str, dict[str, str]]:
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "gpio-control-voltage-fixture/"
    return {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}


def test_gpio_control_voltage_lane_uses_only_reviewed_fixture_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    image = "ghcr.io/kicad/kicad:10.0.0"
    pinned = image + "@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = {
        "control": gpio_control_voltage_netlist(output_rail="+3V3", input_rail="+5V"),
        "fault": gpio_control_voltage_netlist(),
    }

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == tmp_path.resolve()
        assert timeout == 600
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert pinned in argv

        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in source_directory.iterdir()} == {
            "control.kicad_sch",
            "fault.kicad_sch",
        }
        for case in observed:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} export {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-11-05T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    monkeypatch.setattr(lane, "selected_config", lambda *_args: config)
    monkeypatch.setattr(lane, "pinned_image", lambda _image: pinned)
    monkeypatch.setattr(lane, "run_command", fake_run_command)
    monkeypatch.setattr(
        lane,
        "read_netlist",
        lambda path: observed[path.name.split(".", maxsplit=1)[0]].model_copy(
            update={
                "component_symbols": {
                    "U1": "Synthetic:GpioController",
                    "U2": "Synthetic:ControlReceiver",
                }
            }
        ),
    )

    log = HostedLog(root, "gpio-control-voltage-fixture-unit")
    lane.gpio_control_voltage_native_fixture_lane(root, project="synthetic", image=image, log=log)

    results = _stage_results(log)
    assert set(results) == {
        "gpio-control-voltage-fixture/native-export",
        "gpio-control-voltage-fixture/control",
        "gpio-control-voltage-fixture/fault",
    }
    assert results["gpio-control-voltage-fixture/control"]["findings"] == 0
    assert results["gpio-control-voltage-fixture/fault"]["findings"] == 1
    assert results["gpio-control-voltage-fixture/fault"]["evidence"]
    for case in lane.FIXTURE_SOURCE_HASHES:
        result = results[f"gpio-control-voltage-fixture/{case}"]
        assert result["source_sha256"] == lane.FIXTURE_SOURCE_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["repeatable"] == "true"
        assert_native_fixture_mounts(root, result["command_receipt"])


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_GPIO_CONTROL_VOLTAGE_FIXTURES") != "1",
    reason="GPIO control-voltage fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.design_lint_rule(rule_id="power.gpio_to_control_input_voltage_review")
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_gpio_control_voltage_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = lane.selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-gpio-control-voltage-{project}")
    lane.gpio_control_voltage_native_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )
    results = _stage_results(log)
    assert set(results) == {
        "gpio-control-voltage-fixture/native-export",
        "gpio-control-voltage-fixture/control",
        "gpio-control-voltage-fixture/fault",
    }
    assert results["gpio-control-voltage-fixture/native-export"]["status"] == "PASS"
    assert results["gpio-control-voltage-fixture/control"]["findings"] == 0
    assert results["gpio-control-voltage-fixture/fault"]["findings"] == 1
    assert results["gpio-control-voltage-fixture/fault"]["evidence"]
    for case in lane.FIXTURE_SOURCE_HASHES:
        result = results[f"gpio-control-voltage-fixture/{case}"]
        assert result["kicad_version"] == version
        assert result["source_sha256"] == lane.FIXTURE_SOURCE_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["repeatable"] == "true"
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
