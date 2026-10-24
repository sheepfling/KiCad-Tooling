"""Exact-version native regressions for mapped CAN resistor-array channels."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    can_termination_array_native_fixture_lane,
)
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

SOURCE_HASHES = {
    "control": "1f014e79a42f45d5b08d3ef8394dd3b38e992c2af7a67c987c067afa77c3a186",
    "fault": "cae3faf3cba68758c3ed35755d49b96088799922c3c45af3fdc644f5d6d05a2d",
}
REQUIREMENT_HASH = "5c1fc55b40a292e32534aff67e3e17e535edad6e2f10d86fe2a3fe67bba3b872"


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
    prefix = "can-termination-array-fixture/"
    return {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES") != "1",
    reason="native CAN termination-array fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
def test_native_can_termination_array_fault_and_control(
    native_project_root: Path, project: str, version: str, image: str
) -> None:
    config = selected_config(native_project_root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(native_project_root, f"native-can-array-{project}")
    can_termination_array_native_fixture_lane(
        native_project_root,
        project=project,
        image=config.image,
        log=log,
    )

    results = _stage_results(log)
    assert set(results) == {
        "can-termination-array-fixture/native-export",
        "can-termination-array-fixture/control",
        "can-termination-array-fixture/fault",
    }
    assert results["can-termination-array-fixture/native-export"]["status"] == "PASS"
    expected = {
        "control": ("PASS", "PASS", "PASS"),
        "fault": ("PASS", "PASS", "FAIL"),
    }
    for case, statuses in expected.items():
        result = results[f"can-termination-array-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert (result["signal_pins"], result["unlisted_direct"], result["array_path"]) == statuses
        assert result["source_sha256"] == SOURCE_HASHES[case]
        assert result["requirement_sha256"] == REQUIREMENT_HASH
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert_native_fixture_mounts(native_project_root, result["command_receipt"])
