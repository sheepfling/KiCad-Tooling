"""Exact-version native acceptance for named power-pin net-role review."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES") != "1",
    reason="native power pin-role fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_named_power_pin_fault_and_control_export_repeatably(
    hosted_reference_root: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, power_pin_net_role_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    root = hosted_reference_root
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]

    log = HostedLog(root, f"native-power-pin-net-role-{project}")
    power_pin_net_role_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    passed = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-pin-net-role/") and item.get("status") == "PASS"
    }

    assert set(passed) == {
        "power-pin-net-role/native-export",
        "power-pin-net-role/fault",
        "power-pin-net-role/control",
    }
    assert passed["power-pin-net-role/native-export"]["kicad_version"] == version
    assert passed["power-pin-net-role/native-export"]["image"] == expected_images[project]
    fault = passed["power-pin-net-role/fault"]
    control = passed["power-pin-net-role/control"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "U1.1: VDD pin assigned to GND"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        receipt = root / result["command_receipt"]
        assert receipt.is_file()
