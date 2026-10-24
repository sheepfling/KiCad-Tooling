"""Exact-version export coverage for partially assigned Ethernet management pairs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.ethernet_management_unconnected_pin"
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
    os.environ.get("KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_UNCONNECTED_FIXTURES") != "1",
    reason="native Ethernet management-open fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_ethernet_management_open_pin_fault_and_connected_control_repeat(
    hosted_reference_root: Path, project: str, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_ethernet_label import ethernet_label_fixture_lane
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.hwrepo.electrical import selected_config

    root = hosted_reference_root
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-ethernet-management-unconnected-{project}")
    ethernet_label_fixture_lane(
        root,
        project=project,
        image=config.image,
        log=log,
        feature="management_unconnected",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("ethernet-management-unconnected-fixture/")
    }

    assert set(results) == {
        "ethernet-management-unconnected-fixture/native-export",
        "ethernet-management-unconnected-fixture/control",
        "ethernet-management-unconnected-fixture/fault",
    }
    control = results["ethernet-management-unconnected-fixture/control"]
    fault = results["ethernet-management-unconnected-fixture/fault"]
    assert control["findings"] == "none"
    assert fault["findings"] == "U1.5: MDC is open while MDIO U1.6 is assigned to ETH_MDIO"
    native_export = results["ethernet-management-unconnected-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (control, fault):
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert len(result["source_sha256"]) == 64
