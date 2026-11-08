"""Exact-version native exports for Ethernet MDC/MDIO connector review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.ethernet_management_generic_connector_pair_review"
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

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_GENERIC_CONNECTOR_FIXTURES") != "1",
    reason="native Ethernet management connector fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_ethernet_management_generic_connector_fault_and_control_repeat(
    hosted_reference_root: Path,
    project: str,
    version: str,
    image: str,
) -> None:
    from kicad_tooling.ci_hosted_ethernet_label import ethernet_label_fixture_lane

    root = hosted_reference_root
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-ethernet-management-generic-connector-{project}")
    ethernet_label_fixture_lane(
        root,
        project=project,
        image=config.image,
        log=log,
        feature="management_generic_connector",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("ethernet-management-generic-connector-fixture/")
    }

    assert set(results) == {
        "ethernet-management-generic-connector-fixture/native-export",
        "ethernet-management-generic-connector-fixture/control",
        "ethernet-management-generic-connector-fixture/fault",
    }
    native_export = results["ethernet-management-generic-connector-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    assert results["ethernet-management-generic-connector-fixture/control"]["findings"] == "none"
    control_contacts = json.loads(
        results["ethernet-management-generic-connector-fixture/control"]["other_connector_contacts"]
    )
    assert control_contacts == {}
    fault = results["ethernet-management-generic-connector-fixture/fault"]
    assert fault["findings"] == "J1: generic pins match Ethernet MDC/MDIO management nets"
    assert json.loads(fault["other_connector_contacts"]) == {
        "J1: generic pins match Ethernet MDC/MDIO management nets": [
            "J1.3 function=Pin_3 nets=PORT_RX_POS",
            "J1.4 function=Pin_4 nets=PORT_RX_NEG",
            "J1.5 function=GND nets=GND",
        ],
    }
    for result in (results["ethernet-management-generic-connector-fixture/control"], fault):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
