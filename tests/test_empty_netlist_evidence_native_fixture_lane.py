"""Exact-version native evidence-integrity regression for empty netlists."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, empty_netlist_evidence_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_EMPTY_NETLIST_FIXTURES") != "1",
    reason="native empty-netlist evidence fixtures run in the digest-pinned package acceptance lane",
)
def test_native_empty_inventory_trigger_and_nonempty_control_on_supported_images(
    tmp_path: Path,
) -> None:
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
        log = HostedLog(root, f"native-empty-netlist-{project}")
        empty_netlist_evidence_fixture_lane(
            root,
            project=project,
            image=config.image,
            log=log,
        )
        events = tuple(
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("empty-netlist-evidence/")
        }
        assert set(results) == {
            "empty-netlist-evidence/native-export",
            "empty-netlist-evidence/empty",
            "empty-netlist-evidence/nonempty-control",
        }
        assert results["empty-netlist-evidence/native-export"]["status"] == "PASS"
        normalized_hashes_by_version[version] = {}
        for case in ("empty", "nonempty-control"):
            result = results[f"empty-netlist-evidence/{case}"]
            assert result["status"] == "PASS"
            assert result["kicad_version"] == version
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert len(result["source_sha256"]) == 64
            assert len(result["normalized_netlist_sha256"]) == 64
            assert all(
                character in "0123456789abcdef"
                for character in result["source_sha256"] + result["normalized_netlist_sha256"]
            )
            normalized_hashes_by_version[version][case] = result["normalized_netlist_sha256"]
            if case == "empty":
                assert result["component_count"] == 0
                assert result["net_count"] == 0
            else:
                assert result["component_count"] > 0
            assert_native_fixture_mounts(root, result["command_receipt"])
    assert normalized_hashes_by_version["10.0.0"] == normalized_hashes_by_version["10.0.5"]
