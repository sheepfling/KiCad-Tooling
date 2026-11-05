"""Synthetic orchestration and exact-version acceptance for open-drain control lint."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted_open_drain_control_voltage as lane
from kicad_tooling.ci_hosted_support import HostedLog, normalized_netlist_bytes
from kicad_tooling.hwrepo.models import CommandEvidence, NetlistContract
from tests.design_lint_fixtures.open_drain_control_voltage import (
    open_drain_control_voltage_netlist,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.power_lint]

RULE_ID = "power.open_drain_control_input_pullup_voltage_review"
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


def _events(log: HostedLog) -> dict[str, dict[str, str]]:
    lines = log.events.read_text(encoding="utf-8").splitlines()
    prefix = "open-drain-control-voltage-fixture/"
    return {
        item["stage"]: item
        for item in (json.loads(line) for line in lines)
        if item.get("stage", "").startswith(prefix)
    }


def _fixture_netlist(*, fault: bool) -> NetlistContract:
    rail = "+5V" if fault else "+3V3"
    source = open_drain_control_voltage_netlist(
        pullup_rail=rail,
        signal_net="CONTROL_SIGNAL",
        receiver_function="EN",
    )
    symbols = {
        "U1": "Synthetic:GpioController",
        "U2": "Synthetic:ControlReceiver",
        "R1": "Device:R",
    }
    return source.model_copy(update={"component_symbols": symbols})


def test_native_lane_uses_only_reviewed_synthetic_fixture_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    image = "ghcr.io/kicad/kicad:10.0.0"
    pinned = image + "@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = {"control": _fixture_netlist(fault=False), "fault": _fixture_netlist(fault=True)}

    def fake_run_command(root_arg: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root_arg == root
        assert timeout == 600
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert pinned in argv
        assert 'test "$actual" = "10.0.0"' in argv[-1]
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        fixture_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        fixture_directory = Path(fixture_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in fixture_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in lane.FIXTURE_SOURCE_HASHES
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
        lambda path: observed[path.name.split(".", maxsplit=1)[0]],
    )

    log = HostedLog(root, "open-drain-control-voltage-fixture-unit")
    lane.open_drain_control_voltage_fixture_lane(root, project="synthetic", image=image, log=log)

    results = _events(log)
    assert set(results) == {
        "open-drain-control-voltage-fixture/native-export",
        "open-drain-control-voltage-fixture/control",
        "open-drain-control-voltage-fixture/fault",
    }
    assert results["open-drain-control-voltage-fixture/control"]["findings"] == 0
    fault = results["open-drain-control-voltage-fixture/fault"]
    assert fault["findings"] == 1
    assert json.loads(fault["evidence"])["pullup_paths"] == ["R1 (10000 Ω): CONTROL_SIGNAL ↔ +5V"]
    for case in lane.FIXTURE_SOURCE_HASHES:
        result = results[f"open-drain-control-voltage-fixture/{case}"]
        assert result["source_sha256"] == lane.FIXTURE_SOURCE_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["repeatable"] == "true"
        assert_native_fixture_mounts(root, result["command_receipt"])


def test_normalized_netlist_serialization_is_mapping_order_independent() -> None:
    observed = _fixture_netlist(fault=True)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    assert normalized_netlist_bytes(reordered) == normalized_netlist_bytes(observed)


@pytest.fixture
def native_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    return root


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_OPEN_DRAIN_CONTROL_VOLTAGE_FIXTURES") != "1",
    reason="Open-drain control-voltage fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_open_drain_control_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = lane.selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-open-drain-control-{project}")
    lane.open_drain_control_voltage_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )

    results = _events(log)
    assert set(results) == {
        "open-drain-control-voltage-fixture/native-export",
        "open-drain-control-voltage-fixture/control",
        "open-drain-control-voltage-fixture/fault",
    }
    assert results["open-drain-control-voltage-fixture/native-export"]["status"] == "PASS"
    assert results["open-drain-control-voltage-fixture/control"]["findings"] == 0
    assert results["open-drain-control-voltage-fixture/fault"]["findings"] == 1
    assert json.loads(results["open-drain-control-voltage-fixture/fault"]["evidence"])[
        "pullup_paths"
    ] == ["R1 (10000 Ω): CONTROL_SIGNAL ↔ +5V"]
    for case in lane.FIXTURE_SOURCE_HASHES:
        result = results[f"open-drain-control-voltage-fixture/{case}"]
        assert result["kicad_version"] == version
        assert result["source_sha256"] == lane.FIXTURE_SOURCE_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["repeatable"] == "true"
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
