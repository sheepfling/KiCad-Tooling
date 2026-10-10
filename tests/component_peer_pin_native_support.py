"""Exact-version native fixture lane for component peer-pin lint."""

from __future__ import annotations

from pathlib import Path


def _run_native_peer_pin_assignment_lane(kind: str, base: Path) -> None:
    import json

    from kicad_tooling.ci_hosted import (
        HostedLog,
        component_peer_bidirectional_fixture_lane,
        component_peer_power_output_fixture_lane,
        component_peer_signal_input_fixture_lane,
        component_peer_signal_output_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config
    from kicad_tooling.hwrepo.models import DesignLintPolicy
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}
    expected_images = {
        project: PINNED_NATIVE_KICAD_IMAGES[version]
        for project, version in expected_versions.items()
    }
    lanes = {
        "power": ("power-output", component_peer_power_output_fixture_lane),
        "signal": ("signal-output", component_peer_signal_output_fixture_lane),
        "signal-input": ("signal-input", component_peer_signal_input_fixture_lane),
        "bidirectional": ("bidirectional", component_peer_bidirectional_fixture_lane),
    }
    lane_kind, lane = lanes[kind]
    expected_peer_basis_counts = (0, 1) if kind == "power" else (1, 0)
    fixture_lane = f"component-peer-{lane_kind}-fixture"
    source_hashes = {
        "power": {
            "fault": "76cd57afa2e87980e9914a6508066e7197812bacd68241fe9e29ffd618bb9ff4",
            "control": "3b41f81891115ae3e324694f46e41fbe44fb737c86555aa873333aa225b6f34b",
        },
        "signal": {
            "fault": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
            "control": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        },
        "signal-input": {
            "fault": "9d3293d4c7d536549decad392096f118ad0f8cab6e62926572c9784f46f45275",
            "control": "961527991bc45a4545bbf980a7540e81207c0012fa3fbe20772589970b507e15",
        },
        "bidirectional": {
            "fault": "5811d43e0298fb4bd8443bf849e8e75665e693561b4981786e768c0c895f4ea3",
            "control": "1ea8f0a5b92fab8fafd0170adbe6b374f8bc9c24f38b00c00a0ceaafa70e2aa0",
        },
    }[kind]
    for project, version in expected_versions.items():
        root, _ = synthetic_design_lint_project(
            base / project,
            DesignLintPolicy(),
            project_id=project,
            kicad_version=version,
            image=expected_images[project],
        )
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == expected_images[project]
        log = HostedLog(root, f"native-peer-{kind}-{project}")
        lane(root, project=project, image=config.image, log=log)
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
        assert native["image"] == expected_images[project]
        for case, expected_pins, expected_status in (
            ("fault", "U2.2", "REVIEW"),
            ("control", "none", "PASS"),
        ):
            result = results[f"{fixture_lane}/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == expected_status
            assert result["unassigned_pins"] == expected_pins
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert result["peer_coverage_status"] == "EVALUATED"
            assert result["peer_coverage_netlist_sha256"] == result["netlist_sha256"]
            assert result["peer_coverage_exact_symbol_group_count"] == expected_peer_basis_counts[0]
            assert result["peer_coverage_part_id_group_count"] == expected_peer_basis_counts[1]
            expected_count = int(case == "fault")
            assert result["peer_coverage_candidate_count"] == expected_count
            assert result["peer_coverage_deduplicated_candidate_count"] == 0
            assert result["peer_coverage_finding_count"] == expected_count
            assert result["peer_coverage_suppressed_count"] == 0
