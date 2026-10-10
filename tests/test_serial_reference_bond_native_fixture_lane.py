"""Authored serial reference-bond contract and native fault/control checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, serial_peer_reference_bond_fixture_lane
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import SerialPeerAnalysis
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = pytest.mark.design_lint

FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures/design_lint/serial-peer-reference-bond-native"
)
SOURCE_HASHES = {
    "serial-reference-bond-control.kicad_sch": "d6efb587268b8a0dcdbb90eb4401090dcbd6d254742b3e2f718d6df12591c785",
    "serial-reference-bond-fault.kicad_sch": "a8a41b85d776f521df90998e55c5fc8eb55f1afc4839ab50d997b7a9e190aed2",
    "serial-peer-map.json": "db84fc9ef9ebbc019ccd5ced4ee0c8d686af201b9397375d658481caff58b6db",
}
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
BOND_NETLIST_HASHES = {
    "control": "5e530be356d5e584c8ad994eada95b8cfae78031145881890bcfb6cf690ffe80",
    "fault": "748d80edfe816b59c7b876f1d20a816f7de4652172e7e5d19c485f985965c20c",
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


def _assert_schematic_is_balanced(source: str) -> None:
    depth = 0
    quoted = False
    escaped = False
    for character in source:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            assert depth >= 0
    assert depth == 0
    assert not quoted


@pytest.mark.parametrize("filename,expected_hash", SOURCE_HASHES.items())
def test_serial_reference_bond_fixtures_match_reviewed_sources(
    filename: str, expected_hash: str
) -> None:
    path = FIXTURE_ROOT / filename
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_hash
    if path.suffix != ".kicad_sch":
        return

    source = raw.decode("utf-8")
    assert "(wire (pts (xy 65 54.92) (xy 55 54.92))" in source
    assert "(wire (pts (xy 140 54.92) (xy 150 54.92))" in source
    identifiers = re.findall(r'\(uuid\s+"([^"]+)"\)', source)
    assert len(identifiers) == len(set(identifiers))
    _assert_schematic_is_balanced(source)


def test_serial_reference_bond_map_requires_the_authored_fitted_link() -> None:
    requirement = read_model(FIXTURE_ROOT / "serial-peer-map.json", SerialPeerAnalysis)
    assert len(requirement.links) == 1
    link = requirement.links[0]
    assert link.id == "serial-bond"
    assert link.reference_policy == "bonded"
    assert link.reference_bond is not None
    assert link.reference_bond.reference == "R3"


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES") != "1",
    reason="native serial peer fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_serial_reference_bond_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-serial-reference-bond-{project}")
    serial_peer_reference_bond_fixture_lane(
        native_project_root,
        project=project,
        image=image,
        log=log,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("serial-peer-reference-bond-fixture/")
    }
    assert set(results) == {
        "serial-peer-reference-bond-fixture/native-export",
        "serial-peer-reference-bond-fixture/control",
        "serial-peer-reference-bond-fixture/fault",
    }
    native = results["serial-peer-reference-bond-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["authored_map_sha256"] == SOURCE_HASHES["serial-peer-map.json"]
    assert native["normalized_netlist_sha256"] == ";".join(
        f"{case}:{BOND_NETLIST_HASHES[case]}" for case in ("control", "fault")
    )

    for case, expected_status, expected_failure in (
        ("control", "PASS", "none"),
        ("fault", "FAIL", "serial/serial-bond/reference"),
    ):
        result = results[f"serial-peer-reference-bond-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == SOURCE_HASHES[f"serial-reference-bond-{case}.kicad_sch"]
        assert result["authored_map_sha256"] == SOURCE_HASHES["serial-peer-map.json"]
        assert result["normalized_netlist_sha256"] == BOND_NETLIST_HASHES[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["reference_status"] == expected_status
        assert result["failed_checks"] == expected_failure
        assert result["repeatable"] == "true"
        if case == "fault":
            assert "R3.2 is on FLOATING_GND; expected GND_B" in result["reference_detail"]
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
