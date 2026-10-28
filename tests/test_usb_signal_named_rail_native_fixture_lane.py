"""Exact-version native exports for USB named-rail review fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_usb_signal_named_rail import (
    USB_SIGNAL_NAMED_RAIL_TOOLCHAINS,
    usb_signal_named_rail_fixture_lane,
)
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.usb_signal_on_named_rail"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in USB_SIGNAL_NAMED_RAIL_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_SIGNAL_NAMED_RAIL_FIXTURES") != "1",
    reason="native USB named-rail fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_signal_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    root = tmp_path
    log = HostedLog(root, f"native-usb-signal-named-rail-{version}")
    usb_signal_named_rail_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("usb-signal-named-rail-fixture/")
    }

    assert set(results) == {
        "usb-signal-named-rail-fixture/native-export",
        "usb-signal-named-rail-fixture/control",
        "usb-signal-named-rail-fixture/fault",
    }
    fault = results["usb-signal-named-rail-fixture/fault"]
    control = results["usb-signal-named-rail-fixture/control"]
    assert fault["subjects"] == "U1.1: USB_DP on return-like net GND"
    assert control["subjects"] == "none"
    assert fault["erc_errors"] == control["erc_errors"] == "none"
    native_export = results["usb-signal-named-rail-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
