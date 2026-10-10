"""Digest-pinned native acceptance for USB data-path and peer-reference cases."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") != "1",
    reason="native USB data-path fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_usb_data_path_fixture_lane_is_repeatable(
    hosted_reference_root: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, usb_data_path_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    expected_source_hashes = {
        "integrated-direct": "e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27",
        "external-series": "87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f",
        "external-series-reference-bond-control": "5a178e443dcac77c4342d9b3e86a254556f71bbdc1b707bcb2bb23a1459bd9f3",
        "external-series-reference-fault": "25e0cea0682898c5300b27024436717fc9b9b50743ef256b922e98909e0520ab",
        "external-bypass": "0b6173339fc0e2f937247c6eb5aaea1ac51b0b7a26a31058c25119333cb8f0c2",
        "peer-reference-fault": "5af2a1b730701e1167b96f13ccb296c6ff4127e0454404b4e2eef47f5d92b959",
        "peer-reference-control": "0fe232d691405e8ac95ef894a2ece81a3d11ccd9b200f59ff6fcb685d591bd98",
        "usb-c-peer-reference-fault": "b07cb10e9467cb2e34d79cd5ce696a76d9feeb004f3ac218d4d2e0f27a3f510e",
        "usb-c-peer-reference-control": "456f8d1f23735db18f4ec1b0c347cc1ab1d396af3b957c40d9158e535015a70f",
        "usb-multiport-peer-reference-fault": "9cbc4ebc8692b02fc9ef8b6a1723d926536b2b7a74251ff4d37e045cdacae615",
        "usb-multiport-peer-reference-control": "80f5af92083dbc5a3fce319dabb5c80efb535899e482ff6ad952a41f576df0d0",
    }
    root = hosted_reference_root
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-usb-data-path-{project}")
    usb_data_path_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("usb-data-path-fixture/")
    }
    assert set(results) == {
        "usb-data-path-fixture/native-export",
        "usb-data-path-fixture/integrated-direct",
        "usb-data-path-fixture/external-series",
        "usb-data-path-fixture/external-series-reference-bond-control",
        "usb-data-path-fixture/external-series-reference-fault",
        "usb-data-path-fixture/external-bypass",
        "usb-data-path-fixture/peer-reference-fault",
        "usb-data-path-fixture/peer-reference-control",
        "usb-data-path-fixture/usb-c-peer-reference-fault",
        "usb-data-path-fixture/usb-c-peer-reference-control",
        "usb-data-path-fixture/usb-multiport-peer-reference-fault",
        "usb-data-path-fixture/usb-multiport-peer-reference-control",
    }
    for case in ("integrated-direct", "external-series", "external-series-reference-bond-control"):
        result = results[f"usb-data-path-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["usb_path_findings"] == "none"
    bonded_control = results["usb-data-path-fixture/external-series-reference-bond-control"]
    assert bonded_control["usb_reference_findings"] == "none"
    series_peer_fault = results["usb-data-path-fixture/external-series-reference-fault"]
    assert series_peer_fault["status"] == "PASS"
    assert series_peer_fault["lint_status"] == "REVIEW"
    assert series_peer_fault["usb_reference_findings"] == (
        "J1 / U1: USB reference-domain review (port 1)"
    )
    bypass_fault = results["usb-data-path-fixture/external-bypass"]
    assert bypass_fault["status"] == "PASS"
    assert bypass_fault["lint_status"] == "REVIEW"
    assert set(bypass_fault["usb_path_findings"].split(";")) == {
        "external-usb-phy: USB D+ path",
        "external-usb-phy: USB D- path",
    }
    peer_fault = results["usb-data-path-fixture/peer-reference-fault"]
    assert peer_fault["status"] == "PASS"
    assert peer_fault["lint_status"] == "REVIEW"
    assert peer_fault["usb_reference_findings"] == "J1 / U1: USB reference-domain review"
    peer_control = results["usb-data-path-fixture/peer-reference-control"]
    assert peer_control["status"] == "PASS"
    assert peer_control["usb_reference_findings"] == "none"
    usb_c_fault = results["usb-data-path-fixture/usb-c-peer-reference-fault"]
    assert usb_c_fault["status"] == "PASS"
    assert usb_c_fault["lint_status"] == "REVIEW"
    assert usb_c_fault["usb_reference_findings"] == "J1 / U1: USB reference-domain review"
    usb_c_control = results["usb-data-path-fixture/usb-c-peer-reference-control"]
    assert usb_c_control["status"] == "PASS"
    assert usb_c_control["usb_reference_findings"] == "none"
    multiport_fault = results["usb-data-path-fixture/usb-multiport-peer-reference-fault"]
    assert multiport_fault["status"] == "PASS"
    assert multiport_fault["lint_status"] == "REVIEW"
    assert multiport_fault["usb_reference_findings"] == (
        "J1 / U1: USB reference-domain review (port 1);"
        "J2 / U1: USB reference-domain review (port 2)"
    )
    multiport_control = results["usb-data-path-fixture/usb-multiport-peer-reference-control"]
    assert multiport_control["status"] == "PASS"
    assert multiport_control["usb_reference_findings"] == "none"
    for case in (
        "integrated-direct",
        "external-series",
        "external-series-reference-bond-control",
        "external-series-reference-fault",
        "external-bypass",
        "peer-reference-fault",
        "peer-reference-control",
        "usb-c-peer-reference-fault",
        "usb-c-peer-reference-control",
        "usb-multiport-peer-reference-fault",
        "usb-multiport-peer-reference-control",
    ):
        result = results[f"usb-data-path-fixture/{case}"]
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert result["repeatable"] == "true"
        assert result["repeatability_basis"] == "normalized_netlist_contract"
        assert result["source_sha256"] == expected_source_hashes[case]
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
