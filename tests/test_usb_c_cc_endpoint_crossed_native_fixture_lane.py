"""Exact-version native exports for crossed USB-C CC endpoint fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_usb_c_cc_endpoint_crossed import (
    USB_C_CC_ENDPOINT_CROSSED_TOOLCHAINS,
    usb_c_cc_endpoint_crossed_fixture_lane,
)
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in USB_C_CC_ENDPOINT_CROSSED_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_C_CC_ENDPOINT_CROSSED_FIXTURES") != "1",
    reason="native USB-C endpoint-pair fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id="bus.usb_c_cc_endpoint_crossed")
def test_native_usb_c_cc_endpoint_crossed_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-usb-c-cc-endpoint-crossed-{version}")
    usb_c_cc_endpoint_crossed_fixture_lane(tmp_path, version=version, image=image, log=log)
    prefix = "usb-c-cc-endpoint-crossed-fixture/"
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith(prefix)
    }

    assert set(results) == {f"{prefix}native-export", f"{prefix}control", f"{prefix}fault"}
    assert results[f"{prefix}fault"]["subjects"] == (
        "J1/U1: USB-C CC1/CC2 endpoint nets appear crossed"
    )
    assert results[f"{prefix}control"]["subjects"] == "none"
    assert_native_fixture_mounts(tmp_path, results[f"{prefix}native-export"]["command_receipt"])
    for case in ("fault", "control"):
        result = results[f"{prefix}{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
