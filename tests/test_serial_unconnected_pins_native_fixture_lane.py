"""Exact-version KiCad coverage for the open UART/USART pin heuristic."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    serial_unconnected_pin_fixture_lane,
)
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id="bus.serial_unconnected_pin"),
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
CONTROL_SOURCE_SHA256 = "7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060"
FAULT_SOURCE_SHA256 = "c9b769a5fd0bd2c315d76e4b66c25c9de3311146c797a727e25c7ed2cf3f7130"
CONTROL_NETLIST_SHA256 = "b1c218d4e398b4ae9d311732a2a8227887e3e8cce1b9759fbd2aa2f0be4320fd"
FAULT_NETLIST_SHA256 = "ce14fd077113df11185147c8023ee5bd5972678afa429e269b0791342a0a9314"


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
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_UNCONNECTED_PIN_FIXTURES") != "1",
    reason="native serial pin fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_open_serial_pin_fault_and_connected_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-serial-unconnected-{project}")
    serial_unconnected_pin_fixture_lane(native_project_root, project=project, image=image, log=log)
    results = _stage_results(log, "serial-unconnected-pin-fixture/")
    assert set(results) == {
        "serial-unconnected-pin-fixture/native-export",
        "serial-unconnected-pin-fixture/control",
        "serial-unconnected-pin-fixture/fault",
    }

    native = results["serial-unconnected-pin-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["control_source_sha256"] == CONTROL_SOURCE_SHA256
    assert native["fault_source_sha256"] == FAULT_SOURCE_SHA256
    assert native["control_normalized_netlist_sha256"] == CONTROL_NETLIST_SHA256
    assert native["fault_normalized_netlist_sha256"] == FAULT_NETLIST_SHA256
    assert native["repeatable"] == "true"

    control = results["serial-unconnected-pin-fixture/control"]
    assert control["status"] == "PASS"
    assert control["source_sha256"] == CONTROL_SOURCE_SHA256
    assert control["normalized_netlist_sha256"] == CONTROL_NETLIST_SHA256
    assert control["rule_findings"] == "none"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
    assert_native_fixture_mounts(native_project_root, control["command_receipt"])

    fault = results["serial-unconnected-pin-fixture/fault"]
    assert fault["status"] == "PASS"
    assert fault["source_sha256"] == FAULT_SOURCE_SHA256
    assert fault["normalized_netlist_sha256"] == FAULT_NETLIST_SHA256
    assert fault["default_mode"] == "off"
    assert fault["default_disposition"] == "RULE_OFF"
    assert fault["review_mode"] == "review"
    assert fault["review_disposition"] == "OPEN"
    assert fault["findings"] == "J3.1: TX"
    assert "serial_role=TX" in fault["evidence"]
    assert "serial_channel=default" in fault["evidence"]
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
    assert_native_fixture_mounts(native_project_root, fault["command_receipt"])
