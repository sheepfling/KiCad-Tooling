"""Exact-version native exports for the USB D+/D- resistor bridge heuristic."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_usb_data_pair_resistive_bridge import (
    USB_DATA_PAIR_RESISTIVE_BRIDGE_TOOLCHAINS,
    usb_data_pair_resistive_bridge_fixture_lane,
)
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.usb_dp_dm_resistive_bridge"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in USB_DATA_PAIR_RESISTIVE_BRIDGE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DP_DM_RESISTIVE_BRIDGE_FIXTURES") != "1",
    reason="native USB resistor bridge fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_data_pair_resistor_bridge_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-usb-dp-dm-resistive-bridge-{version}")
    usb_data_pair_resistive_bridge_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("usb-dp-dm-resistive-bridge-fixture/")
    }

    assert set(results) == {
        "usb-dp-dm-resistive-bridge-fixture/native-export",
        "usb-dp-dm-resistive-bridge-fixture/control",
        "usb-dp-dm-resistive-bridge-fixture/fault",
    }
    native_export = results["usb-dp-dm-resistive-bridge-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert results["usb-dp-dm-resistive-bridge-fixture/fault"]["subjects"] == (
        "U1: USB data port unindexed D+/D- nets USB_DP and USB_DM are bridged by R1"
    )
    assert results["usb-dp-dm-resistive-bridge-fixture/control"]["subjects"] == "none"
    for case in ("fault", "control"):
        result = results[f"usb-dp-dm-resistive-bridge-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
