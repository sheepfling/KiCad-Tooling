"""Exact-version native export regression for SPI reference review."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, spi_peer_reference_native_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.support import reference_root

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES") != "1",
    reason="native SPI peer-reference fixtures run in the digest-pinned package acceptance lane",
)
def test_native_spi_peer_reference_fault_and_control_on_supported_images(tmp_path: Path) -> None:
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
    normalized_by_version: dict[str, dict[str, str]] = {}
    for project, (version, image) in expected_toolchains.items():
        config = selected_config(root, project)
        assert (config.kicad_version, config.image) == (version, image)
        log = HostedLog(root, f"native-spi-peer-reference-{project}")
        spi_peer_reference_native_fixture_lane(root, project=project, image=config.image, log=log)
        events = tuple(
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("spi-peer-reference-fixture/")
        }
        assert set(results) == {
            "spi-peer-reference-fixture/native-export",
            "spi-peer-reference-fixture/control",
            "spi-peer-reference-fixture/fault",
        }
        assert results["spi-peer-reference-fixture/native-export"]["status"] == "PASS"
        normalized_by_version[version] = {}
        for case, references, disposition, count in (
            ("control", "GND", "COMMON_REFERENCE", "0"),
            ("fault", "GND_A,GND_B", "SPLIT_REFERENCE_REVIEW", "1"),
        ):
            result = results[f"spi-peer-reference-fixture/{case}"]
            assert result["status"] == "PASS"
            assert result["kicad_version"] == version
            assert result["sck"] == "SPI_SCK"
            assert result["supply"] == "+3V3"
            assert result["references"] == references
            assert result["disposition"] == disposition
            assert result["lint_candidate_count"] == count
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            for field in ("source_sha256", "normalized_netlist_sha256"):
                digest = result[field]
                assert len(digest) == 64
                assert all(character in "0123456789abcdef" for character in digest)
            normalized_by_version[version][case] = result["normalized_netlist_sha256"]
            assert_native_fixture_mounts(root, result["command_receipt"])
    assert normalized_by_version["10.0.0"] == normalized_by_version["10.0.5"]
