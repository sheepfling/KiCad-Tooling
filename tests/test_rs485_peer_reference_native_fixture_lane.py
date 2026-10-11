"""Exact-version native regressions for mapped RS-485 peer references."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, rs485_peer_reference_native_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.hosted_ci_support import copy_reference_checkout
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.pcb_native_fixture_support import NATIVE_KICAD_PROJECTS, lane_event

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

SOURCE_HASHES = {
    "reference-control": {
        "schematic": "f1dc5c95eb275ff3fde445f34889112351c24ff2490c940ef863a9cf90deebcf",
        "analysis": "96135ffa15a09b2529b0c383e3171d82ec33c271760413a819ca8c2e9cb956c4",
    },
    "reference-fault": {
        "schematic": "6db1623fc9384949324e86efcb324227a94c9d091637bc2ac9e4d9e02adbb0dc",
        "analysis": "8694c6ee028fdd3aca09eecb1c91e3c938ce35b62385672100d630ad7c2005bb",
    },
}


@pytest.fixture
def native_project_root(tmp_path: Path) -> Path:
    return copy_reference_checkout(tmp_path / "project")


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_RS485_PEER_REFERENCE_FIXTURES") != "1",
    reason="native RS-485 peer-reference fixtures run in digest-pinned package acceptance",
)
@pytest.mark.parametrize(("project", "version"), NATIVE_KICAD_PROJECTS)
def test_native_rs485_peer_reference_fault_and_control(
    native_project_root: Path, project: str, version: str
) -> None:
    config = selected_config(native_project_root, project)
    assert config.kicad_version == version
    log = HostedLog(native_project_root, f"native-rs485-peer-reference-{project}")
    rs485_peer_reference_native_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )

    native = lane_event(log, "rs485-peer-reference-fixture/native-export")
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["repeatable"] == "true"
    assert native["changed_assignments"] == "J3.3"

    expected = {
        "reference-control": ("COMMON_REFERENCE", "GND_A", "0"),
        "reference-fault": ("SPLIT_REFERENCE_REVIEW", "GND_A,GND_B", "1"),
    }
    for case, (disposition, references, candidate_count) in expected.items():
        result = lane_event(log, f"rs485-peer-reference-fixture/{case}")
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["line_1_net"] == "RS485_A"
        assert result["line_2_net"] == "RS485_B"
        assert result["references"] == references
        assert result["disposition"] == disposition
        assert result["lint_candidate_count"] == candidate_count
        assert result["erc_errors"] == "0"
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == SOURCE_HASHES[case]["schematic"]
        assert result["authored_map_sha256"] == SOURCE_HASHES[case]["analysis"]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_erc_sha256"])
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
