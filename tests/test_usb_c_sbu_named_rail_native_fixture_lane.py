"""Exact-version native exports for USB-C SBU named-rail review fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_signal_named_rail import USB_SIGNAL_NAMED_RAIL_TOOLCHAINS

RULE_ID = "bus.usb_c_sbu_signal_on_named_rail"
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
    os.environ.get("KICAD_RUN_NATIVE_USB_C_SBU_NAMED_RAIL_FIXTURES") != "1",
    reason="native USB-C SBU named-rail fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_c_sbu_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.ci_hosted_usb_signal_named_rail import usb_c_sbu_named_rail_fixture_lane

    root = tmp_path
    log = HostedLog(root, f"native-usb-c-sbu-named-rail-{version}")
    usb_c_sbu_named_rail_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("usb-c-sbu-named-rail-fixture/")
    }

    assert set(results) == {
        "usb-c-sbu-named-rail-fixture/native-export",
        "usb-c-sbu-named-rail-fixture/control",
        "usb-c-sbu-named-rail-fixture/fault",
    }
    fault = results["usb-c-sbu-named-rail-fixture/fault"]
    control = results["usb-c-sbu-named-rail-fixture/control"]
    assert fault["subjects"] == (
        "U1.1: SBU1 on return-like net GND;U1.2: SBU2 on supply-like net +3V3"
    )
    assert control["subjects"] == "none"
    assert fault["erc_errors"] == control["erc_errors"] == "none"
    native_export = results["usb-c-sbu-named-rail-fixture/native-export"]
    from tests.native_fixture_support import assert_native_fixture_mounts

    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
