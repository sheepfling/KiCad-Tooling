"""Exact-version native coverage for authored serial peer maps."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    serial_peer_fixture_lane,
    serial_peer_net_label_fixture_lane,
)
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
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
PEER_SOURCE_SHA256 = "7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060"
PEER_NETLIST_SHA256 = "b1c218d4e398b4ae9d311732a2a8227887e3e8cce1b9759fbd2aa2f0be4320fd"
LABEL_SOURCE_SHA256 = "275a14159f90073056e6b0a972f0cd58bcf1439f4b707a0a769b883c05356f03"
LABEL_MAP_SHA256 = "477c059449f5030da6104324c7320ac6aa667cc15c5ef331aeea1df20fe39458"
LABEL_NETLIST_SHA256 = "182122efcca2d6595cafeb398cac44889b54cd187750752201ea1084eacc3d4f"


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
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES") != "1",
    reason="native serial peer fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_serial_peer_roster_fault_partial_and_complete_maps(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-serial-peer-{project}")
    serial_peer_fixture_lane(native_project_root, project=project, image=image, log=log)
    results = _stage_results(log, "serial-peer-fixture/")
    assert set(results) == {
        "serial-peer-fixture/native-export",
        "serial-peer-fixture/unrostered",
        "serial-peer-fixture/partial",
        "serial-peer-fixture/complete",
    }

    native = results["serial-peer-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_sha256"] == PEER_SOURCE_SHA256
    assert native["normalized_netlist_sha256"] == PEER_NETLIST_SHA256
    assert native["normalized_netlist_sha256"] == native["repeat_normalized_netlist_sha256"]
    expected_peers = {
        "unrostered": {"J1", "J2", "J3", "J4"},
        "partial": {"J3", "J4"},
        "complete": set(),
    }
    expected_maps = {
        "unrostered": "none",
        "partial": "a0ed823e11c1612aaa12c8baeca75b1f6b1211ae925970fa2c018c6b8c2a24f4",
        "complete": "abed02ee20a713a60a7a0715133d8e02acf170fbc904faa170649dcb9d98c673",
    }
    expected_pin_functions = "J1.1=TX;J1.2=RX;J2.1=TX;J2.2=RX;J3.1=TX;J3.2=RX;J4.1=TX;J4.2=RX"
    for case, expected_references in expected_peers.items():
        result = results[f"serial-peer-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == ("PASS" if not expected_references else "REVIEW")
        assert {
            finding.split(":", 1)[0]
            for finding in result["findings"].split(";")
            if finding != "none"
        } == expected_references
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == PEER_SOURCE_SHA256
        assert result["authored_map_sha256"] == expected_maps[case]
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["pin_functions"] == expected_pin_functions
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES") != "1",
    reason="native serial peer fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_serial_label_fallback_and_exact_map_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-serial-label-{project}")
    serial_peer_net_label_fixture_lane(native_project_root, project=project, image=image, log=log)
    results = _stage_results(log, "serial-peer-net-label-fixture/")
    assert set(results) == {
        "serial-peer-net-label-fixture/native-export",
        "serial-peer-net-label-fixture/unrostered",
        "serial-peer-net-label-fixture/mapped",
    }

    native = results["serial-peer-net-label-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_sha256"] == LABEL_SOURCE_SHA256
    assert native["normalized_netlist_sha256"] == LABEL_NETLIST_SHA256
    assert native["normalized_netlist_sha256"] == native["repeat_normalized_netlist_sha256"]
    assert native["pin_functions"] == "J5.1=Pin_1;J5.2=Pin_2;U1.1=PA2;U1.2=PA3"

    unrostered = results["serial-peer-net-label-fixture/unrostered"]
    assert unrostered["status"] == "PASS"
    assert unrostered["lint_status"] == "REVIEW"
    assert unrostered["source_sha256"] == LABEL_SOURCE_SHA256
    assert unrostered["authored_map_sha256"] == "none"
    assert unrostered["discovery_basis"] == "net_label"
    assert unrostered["findings"] == "U1: serial-peer map coverage (UART)"
    assert unrostered["repeatable"] == "true"
    assert unrostered["normalized_netlist_sha256"] == unrostered["repeat_normalized_netlist_sha256"]
    assert_native_fixture_mounts(native_project_root, unrostered["command_receipt"])

    mapped = results["serial-peer-net-label-fixture/mapped"]
    assert mapped["status"] == "PASS"
    assert mapped["lint_status"] == "PASS"
    assert mapped["source_sha256"] == LABEL_SOURCE_SHA256
    assert mapped["authored_map_sha256"] == LABEL_MAP_SHA256
    assert mapped["discovery_basis"] == "none"
    assert mapped["findings"] == "none"
    assert mapped["repeatable"] == "true"
    assert mapped["normalized_netlist_sha256"] == mapped["repeat_normalized_netlist_sha256"]
    assert_native_fixture_mounts(native_project_root, mapped["command_receipt"])
