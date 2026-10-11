"""Exact-version native regressions for CAN termination and peer assignment."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    can_peer_assignment_fixture_lane,
    can_termination_native_fixture_lane,
)
from kicad_tooling.ci_hosted_can_peer_reference import can_peer_reference_native_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
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

TERMINATION_HASHES = {
    "control": (
        "f69f9084482ce5455740c4ac33628fd226e5243650acd9a2e022984aec830726",
        "de5d5d2edff5d2f4143bd8a5595734c3ea64f6dfa3844eef626999806fc53c9d",
    ),
    "fault": (
        "0c84ea82f7ff60be1d8a1ea6f2815fe9e6593ad1e8ae192f362c02af73bb8db6",
        "4d0141640743cd0f953fe382941036a396f39b104fe89d9fd1febc43767bacb6",
    ),
}
PEER_HASHES = {
    "peer-control": (
        "9adfa39101f0caaa60bde8ca1770659382d6bfc1677e1b2272847bb76d943135",
        "add4ca19eeac84b2f89733cc3a27aa2ff7a1a8945ed4699e3f35ffb882cdeca4",
    ),
    "peer-fault": (
        "60e310e7faae4cee9b8982b1d2abc5be3e8d6c48d815dd9808ae82e7578ecbc6",
        "337f52c298085c36f4e738f1ba486dceeea15cae32dea6f4094c362f159c8e26",
    ),
}

PEER_REFERENCE_HASHES = {
    "reference-control": "ebd9bddaa27be15635614b76dbf47e1476d02ff75dc0bbf8d06bc69c2b987bcc",
    "reference-fault": "12fc606e4631f4885f2bea51e53ab1ad2a81f4a1f621547a8b869cfa031dd48b",
}


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
    os.environ.get("KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES") != "1",
    reason="native CAN termination fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_can_split_termination_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-can-termination-{project}")
    can_termination_native_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )
    results = _stage_results(log, "can-termination-fixture/")
    assert set(results) == {
        "can-termination-fixture/native-export",
        "can-termination-fixture/control",
        "can-termination-fixture/fault",
    }
    assert results["can-termination-fixture/native-export"]["status"] == "PASS"
    expected_checks = {
        "control": ("PASS", "PASS", "PASS", "PASS"),
        "fault": ("PASS", "PASS", "PASS", "FAIL"),
    }
    for case, expected_statuses in expected_checks.items():
        result = results[f"can-termination-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert (
            result["signal_pins"],
            result["unlisted_direct"],
            result["split_path"],
            result["midpoint_capacitor"],
        ) == expected_statuses
        source_hash, netlist_hash = TERMINATION_HASHES[case]
        assert result["source_sha256"] == source_hash
        assert result["normalized_netlist_sha256"] == netlist_hash
        assert result["repeat_normalized_netlist_sha256"] == netlist_hash
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_PEER_FIXTURES") != "1",
    reason="native CAN peer fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_can_peer_assignment_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-can-peer-{project}")
    can_peer_assignment_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )
    results = _stage_results(log, "can-peer-fixture/")
    assert set(results) == {
        "can-peer-fixture/native-export",
        "can-peer-fixture/peer-control",
        "can-peer-fixture/peer-fault",
    }
    assert results["can-peer-fixture/native-export"]["status"] == "PASS"
    assert results["can-peer-fixture/peer-control"]["lint_status"] == "PASS"
    assert results["can-peer-fixture/peer-control"]["findings"] == "none"
    assert results["can-peer-fixture/peer-fault"]["lint_status"] == "REVIEW"
    assert (
        results["can-peer-fixture/peer-fault"]["findings"] == "bus.can_peer_assignment_divergence"
    )
    warning_types = {"footprint_link_issues", "lib_symbol_issues"}
    for case in ("peer-control", "peer-fault"):
        result = results[f"can-peer-fixture/{case}"]
        source_hash, netlist_hash = PEER_HASHES[case]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["erc_errors"] == "0"
        assert set(result["erc_warning_types"].split(";")) == warning_types
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == source_hash
        assert result["normalized_netlist_sha256"] == netlist_hash
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES") != "1",
    reason="native CAN peer-reference fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_can_peer_reference_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-can-peer-reference-{project}")
    can_peer_reference_native_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )
    results = _stage_results(log, "can-peer-reference-fixture/")
    assert set(results) == {
        "can-peer-reference-fixture/native-export",
        "can-peer-reference-fixture/reference-control",
        "can-peer-reference-fixture/reference-fault",
    }
    assert results["can-peer-reference-fixture/native-export"]["status"] == "PASS"
    expected = {
        "reference-control": ("COMMON_REFERENCE", "GND_A", "0"),
        "reference-fault": ("SPLIT_REFERENCE_REVIEW", "GND_A,GND_B", "1"),
    }
    for case, (disposition, references, candidate_count) in expected.items():
        result = results[f"can-peer-reference-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["canh_net"] == "NET_B"
        assert result["canl_net"] == "NET_A"
        assert result["references"] == references
        assert result["disposition"] == disposition
        assert result["lint_candidate_count"] == candidate_count
        assert result["erc_errors"] == "0"
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == PEER_REFERENCE_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_erc_sha256"])
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
