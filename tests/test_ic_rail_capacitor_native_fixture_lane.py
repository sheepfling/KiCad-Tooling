"""Digest-pinned native acceptance for IC rail-capacitor review."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES") != "1",
    reason="native IC rail-capacitor fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_missing_capacitor_and_controls_export_repeatably(
    hosted_reference_root: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, ic_rail_capacitor_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    root = hosted_reference_root
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    expected_source_hashes = {
        "positive-rail-no-cap": "09ec95768fb247b1ec781a078f585b27eee66ae7e40bc0251cefb7ebef511e7a",
        "positive-rail-cap-control": "2e67336b13f8ff9b62dd4e40bd45a4116e4d825d78f361537ea3693d4e18d4a2",
        "unrecognized-rail-control": "0d42a2f557d2488425a7b1767e7e3b782c4bfe2c2e11bc2344f41513c49c7fb9",
        "source-backed-control": "2a3632b71b5c7bc01b282cb2d23a5b49df5759364a99e588b98b659654c9d45f",
        "source-backed-no-cap": "5db3396470f1e3b8101e428dc25b41c4166f1748e4a68ad88a3ac2757173952a",
        "source-backed-dnp-capacitor": "8184bd9c297b40d0192af1e446206939ec7d5466bc8e306a0292472da7424b6c",
        "custom-capacitor-role-control": "338b39009694575fae172d6691ddd8d17804d74503ad73c374a53661373e789d",
        "custom-capacitor-role-wrong-return": "52edf68703b6fc4052fbb7197778108fc52c0a4ac4195bd533a1d1aaead8669a",
    }
    expected_findings: dict[str, tuple[str, set[str]]] = {
        "positive-rail-no-cap": ("REVIEW", {"+3V3: IC supply decoupling review"}),
        "positive-rail-cap-control": ("PASS", set()),
        "unrecognized-rail-control": ("REVIEW", set()),
        "source-backed-control": ("PASS", set()),
        "source-backed-no-cap": ("REVIEW", {"+3V3: IC supply decoupling review"}),
        "source-backed-dnp-capacitor": (
            "REVIEW",
            {"+3V3: IC supply decoupling review"},
        ),
        "custom-capacitor-role-control": ("PASS", set()),
        "custom-capacitor-role-wrong-return": (
            "REVIEW",
            {"+3V3: IC supply decoupling review"},
        ),
    }
    expected_source_path_findings = {
        "positive-rail-no-cap": "none",
        "positive-rail-cap-control": "none",
        "unrecognized-rail-control": ("LOCAL_A: power-input source-path review"),
        "source-backed-control": "none",
        "source-backed-no-cap": "none",
        "source-backed-dnp-capacitor": "none",
        "custom-capacitor-role-control": "none",
        "custom-capacitor-role-wrong-return": "none",
    }
    expected_power_pin_not_driven = {
        "positive-rail-no-cap",
        "positive-rail-cap-control",
        "unrecognized-rail-control",
    }
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-ic-rail-capacitor-{project}")
    ic_rail_capacitor_fixture_lane(
        root,
        project=project,
        image=config.image,
        log=log,
    )
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("ic-rail-cap-fixture/")
    }
    assert set(results) == {
        "ic-rail-cap-fixture/native-export",
        "ic-rail-cap-fixture/positive-rail-no-cap",
        "ic-rail-cap-fixture/positive-rail-cap-control",
        "ic-rail-cap-fixture/unrecognized-rail-control",
        "ic-rail-cap-fixture/source-backed-control",
        "ic-rail-cap-fixture/source-backed-no-cap",
        "ic-rail-cap-fixture/source-backed-dnp-capacitor",
        "ic-rail-cap-fixture/custom-capacitor-role-control",
        "ic-rail-cap-fixture/custom-capacitor-role-wrong-return",
    }
    native = results["ic-rail-cap-fixture/native-export"]
    assert native["status"] == "PASS"
    for case, (expected_status, expected_case_findings) in expected_findings.items():
        result = results[f"ic-rail-cap-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["lint_status"] == expected_status
        assert result["source_path_findings"] == expected_source_path_findings[case]
        assert (
            set(result["capacitor_findings"].split(";"))
            if result["capacitor_findings"] != "none"
            else set()
        ) == expected_case_findings
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert result["repeatable"] == "true"
        assert result["source_sha256"] == expected_source_hashes[case]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
        assert result["power_pin_not_driven"] == (
            "true" if case in expected_power_pin_not_driven else "false"
        )
        assert ("power_pin_not_driven" in result["native_erc_types"].split(",")) == (
            case in expected_power_pin_not_driven
        )
        assert result["native_erc_error_types"] == (
            "power_pin_not_driven" if case in expected_power_pin_not_driven else "none"
        )
        receipt = root / result["command_receipt"]
        assert receipt.is_file()
        command = json.loads(receipt.read_text())
        mounts = tuple(
            command["argv"][index + 1]
            for index, item in enumerate(command["argv"][:-1])
            if item == "-v"
        )
        assert len(mounts) == 2
        assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
        assert sum(item.endswith(":/output:rw") for item in mounts) == 1
