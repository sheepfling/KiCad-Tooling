"""Exact-version native exports for USB-C CC1/CC2 same-net fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_c_cc_same_net import USB_C_CC_SAME_NET_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.usb_c_cc_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in USB_C_CC_SAME_NET_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_C_CC_SAME_NET_FIXTURES") != "1",
    reason="native USB-C same-net fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_c_cc_same_net_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.ci_hosted_usb_c_cc_same_net import usb_c_cc_same_net_fixture_lane

    log = HostedLog(tmp_path, f"native-usb-c-cc-same-net-{version}")
    usb_c_cc_same_net_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("usb-c-cc1-cc2-same-net-fixture/")
    }

    assert set(results) == {
        "usb-c-cc1-cc2-same-net-fixture/native-export",
        "usb-c-cc1-cc2-same-net-fixture/control",
        "usb-c-cc1-cc2-same-net-fixture/fault",
    }
    native_export = results["usb-c-cc1-cc2-same-net-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert results["usb-c-cc1-cc2-same-net-fixture/fault"]["subjects"] == (
        "J1: USB-C CC1/CC2 pins share CC_SHARED"
    )
    assert results["usb-c-cc1-cc2-same-net-fixture/control"]["subjects"] == "none"
    for case in ("fault", "control"):
        result = results[f"usb-c-cc1-cc2-same-net-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
