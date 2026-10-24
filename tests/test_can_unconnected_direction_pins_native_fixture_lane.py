"""Exact-version KiCad coverage for an open CAN/FDCAN direction pin."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, can_unconnected_direction_pin_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id="bus.can_unconnected_direction_pin"),
]

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
CONTROL_SOURCE_SHA256 = "3333488238d746ef18c6ace63e6b3cd0e65f1b48c7aca959f4edf76d561baaf7"
FAULT_SOURCE_SHA256 = "e653fe6f2c2dc9378b4a410212320706481ba5d1f78bd991acd1ec745ee1a3d6"


@pytest.fixture
def native_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    return root


def _stage_results(log: HostedLog, prefix: str) -> dict[str, dict[str, str]]:
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    return {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_UNCONNECTED_DIRECTION_PIN_FIXTURES") != "1",
    reason="native CAN direction fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_open_can_direction_pin_fault_and_connected_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-can-unconnected-direction-{project}")
    can_unconnected_direction_pin_fixture_lane(
        native_project_root,
        project=project,
        image=image,
        log=log,
    )
    results = _stage_results(log, "can-unconnected-direction-fixture/")
    assert set(results) == {
        "can-unconnected-direction-fixture/native-export",
        "can-unconnected-direction-fixture/control",
        "can-unconnected-direction-fixture/fault",
    }

    native = results["can-unconnected-direction-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["control_source_sha256"] == CONTROL_SOURCE_SHA256
    assert native["fault_source_sha256"] == FAULT_SOURCE_SHA256
    assert native["repeatable"] == "true"
    assert_native_fixture_mounts(native_project_root, native["command_receipt"])

    control = results["can-unconnected-direction-fixture/control"]
    assert control["status"] == "PASS"
    assert control["source_sha256"] == CONTROL_SOURCE_SHA256
    assert control["rule_findings"] == "none"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]

    fault = results["can-unconnected-direction-fixture/fault"]
    assert fault["status"] == "PASS"
    assert fault["source_sha256"] == FAULT_SOURCE_SHA256
    assert fault["default_mode"] == "off"
    assert fault["default_disposition"] == "RULE_OFF"
    assert fault["review_mode"] == "review"
    assert fault["review_disposition"] == "OPEN"
    assert fault["rule_findings"] == "U1.1: CAN1_TX"
    assert "can_role=TX" in fault["evidence"]
    assert "can_channel=can:index1" in fault["evidence"]
    assert "paired_pin=U1.2" in fault["evidence"]
    assert "paired_net=CAN1_RX" in fault["evidence"]
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
