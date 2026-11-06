"""Exact-version exports for the USB-C VBUS capacitor review heuristic."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_usb_c_vbus_cap_review import (
    usb_c_vbus_capacitance_review_fixture_lane,
)
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "bus.usb_c_vbus_capacitance_review"
PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in KICAD_10_NATIVE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_C_VBUS_CAP_REVIEW_FIXTURES") != "1",
    reason="native USB-C VBUS capacitor fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_usb_c_vbus_capacitance_review_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:
    log = HostedLog(tmp_path, f"native-usb-c-vbus-cap-review-{version}")
    usb_c_vbus_capacitance_review_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    result = next(
        item
        for item in events
        if item.get("stage") == "usb-c-vbus-cap-review/native-export"
        and item.get("status") == "PASS"
    )
    assert result["kicad_version"] == version
    assert result["image"] == image
    assert result["finding_subjects"] == ("J1: USB-C VBUS has no recognized return capacitor")
    assert result["erc_errors"] == "none"
    assert result["repeatable"] == "true"
    assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
    assert_native_fixture_mounts(tmp_path, result["command_receipt"])
