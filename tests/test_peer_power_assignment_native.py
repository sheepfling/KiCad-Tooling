"""Pinned native fixtures for part-ID component peer power assignment."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import DesignLintPolicy

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint, pytest.mark.power_lint]


def test_native_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/component-peer-power-assignment-native"
    )
    expected = {
        "fault.kicad_sch": "2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6",
        "control.kicad_sch": "23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d",
    }

    assert {
        filename: hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def _run_native_part_id_peer_power_assignment_lane(base: Path) -> None:
    import json

    from kicad_tooling.ci_hosted import HostedLog, component_peer_power_assignment_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.synthetic_design_lint_project import synthetic_design_lint_project

    expected_projects = {
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
    source_hashes = {
        "fault": "2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6",
        "control": "23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d",
    }
    fixture_lane = "component-peer-power-assignment-fixture"

    for project, (version, image) in expected_projects.items():
        root, _ = synthetic_design_lint_project(
            base / project,
            DesignLintPolicy(),
            project_id=project,
            kicad_version=version,
            image=image,
        )
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == image
        log = HostedLog(root, f"native-peer-power-assignment-{project}")
        component_peer_power_assignment_fixture_lane(
            root, project=project, image=config.image, log=log
        )
        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith(fixture_lane + "/")
        }
        assert set(results) == {
            f"{fixture_lane}/native-export",
            f"{fixture_lane}/fault",
            f"{fixture_lane}/control",
        }
        native = results[f"{fixture_lane}/native-export"]
        assert native["status"] == "PASS"
        assert native["kicad_version"] == version
        assert native["image"] == image

        for case, expected_findings, expected_status, decoupling_nets in (
            ("fault", "ground/return;supply", "REVIEW", "SYNTHETIC_NET_A;SYNTHETIC_NET_B"),
            ("control", "none", "REVIEW", "SYNTHETIC_NET_1"),
        ):
            result = results[f"{fixture_lane}/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == expected_status
            assert result["peer_power_findings"] == expected_findings
            assert result["independent_decoupling_findings"] == decoupling_nets
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_part_id_peer_power_assignment_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    _run_native_part_id_peer_power_assignment_lane(tmp_path)
