"""Exact-version KiCad export checks for USB data pin/name polarity review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

RULE_ID = "bus.usb_data_polarity_label_mismatch"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES") != "1",
    reason="native USB data polarity fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_data_polarity_fault_and_control_repeat(
    hosted_reference_root: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.ci_hosted_usb_data_polarity import usb_data_polarity_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    root = hosted_reference_root
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-usb-data-polarity-{project}")
    usb_data_polarity_fixture_lane(root, project=project, image=config.image, log=log)
    results = {
        item["stage"]: item
        for item in (json.loads(line) for line in log.events.read_text().splitlines())
        if item.get("stage", "").startswith("usb-data-polarity-fixture/")
    }

    assert set(results) == {
        "usb-data-polarity-fixture/native-export",
        "usb-data-polarity-fixture/control",
        "usb-data-polarity-fixture/fault",
    }
    fault = results["usb-data-polarity-fixture/fault"]
    control = results["usb-data-polarity-fixture/control"]
    assert fault["polarity_findings"] == "J1.1: D+ on USB_D-;J1.2: D- on USB_D+"
    assert control["polarity_findings"] == "none"
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
