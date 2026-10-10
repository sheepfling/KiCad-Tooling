"""Exact-version native regression for mapped I2C pull-up arrays."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, i2c_pullup_native_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES") != "1",
    reason="native I2C pull-up fixtures run in the digest-pinned package acceptance lane",
)
def test_native_array_channel_fault_and_control_on_supported_images(tmp_path: Path) -> None:
    root = tmp_path / "project"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_toolchains = {
        "controller": (
            "10.0.0",
            (
                "ghcr.io/kicad/kicad:10.0.0@sha256:"
                "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
            ),
        ),
        "raspberry-pi-status-led": (
            "10.0.5",
            (
                "ghcr.io/kicad/kicad:10.0.5@sha256:"
                "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
            ),
        ),
    }
    normalized_hashes_by_version: dict[str, dict[str, str]] = {}
    for project, (version, image) in expected_toolchains.items():
        config = selected_config(root, project)
        assert (config.kicad_version, config.image) == (version, image)
        log = HostedLog(root, f"native-i2c-pullup-{project}")
        i2c_pullup_native_fixture_lane(root, project=project, image=config.image, log=log)
        events = tuple(
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("i2c-pullup-fixture/")
        }
        assert set(results) == {
            "i2c-pullup-fixture/native-export",
            "i2c-pullup-fixture/control",
            "i2c-pullup-fixture/fault",
        }
        assert results["i2c-pullup-fixture/native-export"]["status"] == "PASS"
        control = results["i2c-pullup-fixture/control"]
        fault = results["i2c-pullup-fixture/fault"]
        normalized_hashes_by_version[version] = {
            "control": control["normalized_netlist_sha256"],
            "fault": fault["normalized_netlist_sha256"],
        }
        assert (control["sda"], control["scl"]) == ("PASS", "PASS")
        assert (fault["sda"], fault["scl"]) == ("FAIL", "PASS")
        for result in (control, fault):
            assert result["status"] == "PASS"
            assert result["kicad_version"] == version
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            digests = (result["source_sha256"], result["normalized_netlist_sha256"])
            assert all(len(digest) == 64 for digest in digests)
            assert all(
                character in "0123456789abcdef" for digest in digests for character in digest
            )
            assert_native_fixture_mounts(root, result["command_receipt"])
    assert normalized_hashes_by_version["10.0.0"] == normalized_hashes_by_version["10.0.5"]
