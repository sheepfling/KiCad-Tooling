"""Exact-version native exports for USB 2.0 D+/D- same-net fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_data_same_net import USB_DATA_SAME_NET_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.usb_dp_dm_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in USB_DATA_SAME_NET_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DP_DM_SAME_NET_FIXTURES") != "1",
    reason="native USB same-net fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_dp_dm_same_net_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.ci_hosted_usb_data_same_net import usb_dp_dm_same_net_fixture_lane

    log = HostedLog(tmp_path, f"native-usb-dp-dm-same-net-{version}")
    usb_dp_dm_same_net_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("usb-dp-dm-same-net-fixture/")
    }

    assert set(results) == {
        "usb-dp-dm-same-net-fixture/native-export",
        "usb-dp-dm-same-net-fixture/control",
        "usb-dp-dm-same-net-fixture/fault",
    }
    native_export = results["usb-dp-dm-same-net-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert results["usb-dp-dm-same-net-fixture/fault"]["subjects"] == (
        "U1: USB data port unindexed D+/D- pins share USB_SHARED"
    )
    assert results["usb-dp-dm-same-net-fixture/control"]["subjects"] == "none"
    for case in ("fault", "control"):
        result = results[f"usb-dp-dm-same-net-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
