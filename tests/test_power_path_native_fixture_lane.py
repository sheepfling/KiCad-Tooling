"""Digest-pinned native acceptance for synthetic power-path topology cases."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, power_path_fixture_lane

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PATH_FIXTURES") != "1",
    reason="native power-path fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_mapped_ferrite_path_control_and_wrong_rail_fault(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.support import reference_root

    root = tmp_path / project
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    expected_source_hashes = {
        "control": "2f81814b683e60208a405e1bed48ea99e72578590ca5b5d3cf5f36217091e83b",
        "fault": "8a042a236f587869ee1da38a04f1dcb8e9f67b38e71b83d32e6000dd0ee7e8f1",
        "diode-control": "b750aa6d2f2a35c8e377108d9ff170dba4ac8c916c9bf45ae5df2ee63f2d3a6e",
        "diode-reverse-fault": "3ccc41b19fefe5cc4d2bd4dcdeab63b1a4818b8ea08c06dfa271623097d71d01",
        "schottky-diode-control": "e445d0500527b88bdbe5e8c7c6b48190c5d3b3b15199b564c4167fdf3d2cecb6",
        "bridged-jumper-control": "b01f9bd7ae106c81928443606fd88e4db34c76a024cf647d264ef0738d91f57d",
        "open-jumper-fault": "0af7bfb07703ced61d99d4769201f164193f34eaeef84611ddb767f234119e59",
        "bridged-three-pin12-control": "c952212ba4302cb5b1c613b2b788b7d5be16dab5d792f21b118af8aa5e3db02b",
        "bridged-three-pin123-control": "87bf21582a48fb399e9eb0739e78140ad0eb721d2622f81ed0db752d34307abd",
        "bridged-three-pin12-unbridged-terminal-fault": "c246a84d7d12059c927a8ecda26c5383e826d89dbee47f7c86b152491cd1f214",
        "isolated-control": "efed3c0180961a10925e61df2a9e147e85d6b7fd13f0db8c32d84a4e77b30970",
        "custom-capacitor-control": "333c63e0a3b629d5d2769d53321f11fe7bb7c21bdf4c47af705994d0d357a4fc",
        "custom-capacitor-fault": "3c70ab0b0a1f6d8846e424d286ba461c5645371067728c44e0f216b63ef5bca9",
        "opaque-capacitor-fault": "46dfad381efae9194734a9b88cad6adf2ead95b9d254436bb060c12e2265eb35",
        "external-source-control": "dd3c7433c0070a1f00a30ed8646085c4a4cd349010c9b2216486f8bff2707539",
        "dnp-external-source-fault": "e1e77f3335c5e5cec3bd3805f87feb644f5ba6486555cf3aba17199ea10f9b30",
        "alternate-source-control": "42d4afac7c4f409b706f09ac5673efaeb0847f0e2042eea4e4623873be77c752",
        "both-sources-dnp-fault": "bbd21576756b29d75c60f1074326309f22741c12f2e699c00fe6b9a4b153020b",
    }
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-power-path-{project}")
    power_path_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-path-fixture/")
    }
    assert set(results) == {
        "power-path-fixture/native-export",
        "power-path-fixture/control",
        "power-path-fixture/fault",
        "power-path-fixture/diode-control",
        "power-path-fixture/diode-reverse-fault",
        "power-path-fixture/schottky-diode-control",
        "power-path-fixture/bridged-jumper-control",
        "power-path-fixture/open-jumper-fault",
        "power-path-fixture/bridged-three-pin12-control",
        "power-path-fixture/bridged-three-pin123-control",
        "power-path-fixture/bridged-three-pin12-unbridged-terminal-fault",
        "power-path-fixture/isolated-control",
        "power-path-fixture/custom-capacitor-control",
        "power-path-fixture/custom-capacitor-fault",
        "power-path-fixture/opaque-capacitor-fault",
        "power-path-fixture/external-source-control",
        "power-path-fixture/dnp-external-source-fault",
        "power-path-fixture/alternate-source-control",
        "power-path-fixture/both-sources-dnp-fault",
    }
    control = results["power-path-fixture/control"]
    fault = results["power-path-fixture/fault"]
    bridged_jumper = results["power-path-fixture/bridged-jumper-control"]
    open_jumper = results["power-path-fixture/open-jumper-fault"]
    bridged_three_pin12 = results["power-path-fixture/bridged-three-pin12-control"]
    bridged_three_pin123 = results["power-path-fixture/bridged-three-pin123-control"]
    bridged_three_pin_fault = results[
        "power-path-fixture/bridged-three-pin12-unbridged-terminal-fault"
    ]
    diode_control = results["power-path-fixture/diode-control"]
    diode_fault = results["power-path-fixture/diode-reverse-fault"]
    schottky_control = results["power-path-fixture/schottky-diode-control"]
    isolated = results["power-path-fixture/isolated-control"]
    custom_control = results["power-path-fixture/custom-capacitor-control"]
    custom_fault = results["power-path-fixture/custom-capacitor-fault"]
    opaque_fault = results["power-path-fixture/opaque-capacitor-fault"]
    external_control = results["power-path-fixture/external-source-control"]
    dnp_external_fault = results["power-path-fixture/dnp-external-source-fault"]
    alternate_source = results["power-path-fixture/alternate-source-control"]
    both_sources_dnp = results["power-path-fixture/both-sources-dnp-fault"]
    assert control["power_path_findings"] == "none"
    assert "source-through-bead-to-load" in fault["power_path_findings"]
    assert control["lint_status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "FB1.1 is assigned to GND; expected VIN" in fault["power_path_details"]
    assert diode_control["source_sha256"] == expected_source_hashes["diode-control"]
    assert diode_fault["source_sha256"] == expected_source_hashes["diode-reverse-fault"]
    assert schottky_control["source_sha256"] == expected_source_hashes["schottky-diode-control"]
    assert diode_control["unmapped_lint_status"] == "PASS"
    assert diode_control["unmapped_power_input_findings"] == "none"
    assert schottky_control["unmapped_lint_status"] == "PASS"
    assert schottky_control["unmapped_power_input_findings"] == "none"
    assert diode_fault["unmapped_lint_status"] == "REVIEW"
    assert (
        diode_fault["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert bridged_jumper["unmapped_lint_status"] == "PASS"
    assert bridged_jumper["unmapped_power_input_findings"] == "none"
    assert open_jumper["unmapped_lint_status"] == "REVIEW"
    assert (
        open_jumper["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert bridged_three_pin12["unmapped_lint_status"] == "PASS"
    assert bridged_three_pin12["unmapped_power_input_findings"] == "none"
    assert bridged_three_pin123["unmapped_lint_status"] == "PASS"
    assert bridged_three_pin123["unmapped_power_input_findings"] == "none"
    assert bridged_three_pin_fault["unmapped_lint_status"] == "REVIEW"
    assert (
        bridged_three_pin_fault["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert fault["other_findings"] == "none"
    assert control["unmapped_power_input_findings"] == "none"
    assert (
        fault["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert control["unmapped_lint_status"] == "PASS"
    assert fault["unmapped_lint_status"] == "REVIEW"
    assert isolated["power_path_findings"] == "none"
    assert isolated["lint_status"] == "PASS"
    assert isolated["unmapped_lint_status"] == "PASS"
    assert isolated["unmapped_power_input_findings"] == "none"
    assert isolated["return_nets"] == "ISO_RETURN"
    assert custom_control["power_path_findings"] == "none"
    assert custom_control["unmapped_lint_status"] == "PASS"
    assert custom_control["unmapped_power_input_findings"] == "none"
    assert custom_fault["lint_status"] == "REVIEW"
    assert custom_fault["unmapped_lint_status"] == "REVIEW"
    assert custom_fault["unmapped_other_findings"] == "none"
    assert (
        "power.input_without_supported_source_path:VLOAD"
        in custom_fault["unmapped_power_input_findings"]
    )
    assert opaque_fault["lint_status"] == "REVIEW"
    assert opaque_fault["unmapped_lint_status"] == "REVIEW"
    assert opaque_fault["unmapped_power_input_findings"] == "none"
    assert (
        opaque_fault["unmapped_other_findings"]
        == "power.ic_rail_without_fitted_capacitor:VLOAD: IC supply decoupling review"
    )
    assert external_control["lint_status"] == "PASS"
    assert external_control["unmapped_lint_status"] == "PASS"
    assert external_control["unmapped_power_input_findings"] == "none"
    assert dnp_external_fault["lint_status"] == "REVIEW"
    assert dnp_external_fault["unmapped_lint_status"] == "REVIEW"
    assert (
        dnp_external_fault["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert dnp_external_fault["unmapped_other_findings"] == "none"
    assert external_control["source_population"] == "FITTED"
    assert dnp_external_fault["source_population"] == "DNP"
    assert alternate_source["source_population"] == "J1_DNP_J2_FITTED"
    assert alternate_source["lint_status"] == "PASS"
    assert alternate_source["unmapped_lint_status"] == "PASS"
    assert alternate_source["unmapped_power_input_findings"] == "none"
    assert alternate_source["erc_error_types"] == "none"
    assert both_sources_dnp["source_population"] == "BOTH_DNP"
    assert both_sources_dnp["lint_status"] == "REVIEW"
    assert both_sources_dnp["unmapped_lint_status"] == "REVIEW"
    assert (
        both_sources_dnp["unmapped_power_input_findings"]
        == "power.input_without_supported_source_path:VLOAD: power-input source-path review"
    )
    assert both_sources_dnp["unmapped_other_findings"] == "none"
    assert both_sources_dnp["erc_error_types"] == "none"
    assert external_control["erc_error_types"] == "none"
    assert dnp_external_fault["erc_error_types"] == "none"
    assert control["erc_error_types"] == "none"
    assert fault["erc_error_types"] == "none"
    assert control["erc_error_types"] == fault["erc_error_types"]
    assert control["erc_violation_types"] == fault["erc_violation_types"]
    assert control["kicad_version"] == version
    assert fault["kicad_version"] == version
    for case, result in (
        ("control", control),
        ("fault", fault),
        ("isolated-control", isolated),
        ("bridged-jumper-control", bridged_jumper),
        ("open-jumper-fault", open_jumper),
        ("bridged-three-pin12-control", bridged_three_pin12),
        ("bridged-three-pin123-control", bridged_three_pin123),
        ("bridged-three-pin12-unbridged-terminal-fault", bridged_three_pin_fault),
        ("custom-capacitor-control", custom_control),
        ("custom-capacitor-fault", custom_fault),
        ("opaque-capacitor-fault", opaque_fault),
        ("external-source-control", external_control),
        ("dnp-external-source-fault", dnp_external_fault),
        ("alternate-source-control", alternate_source),
        ("both-sources-dnp-fault", both_sources_dnp),
    ):
        assert result["image"] == expected_images[project]
        assert result["source_sha256"] == expected_source_hashes[case]
        assert result["repeatable"] == "true"
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
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
