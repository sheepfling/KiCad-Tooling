"""Exact-version exports for Ethernet management pins assigned to named rails."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_ethernet_label import ETHERNET_LABEL_NATIVE_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.ethernet_management_signal_on_named_rail"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in ETHERNET_LABEL_NATIVE_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_NAMED_RAIL_FIXTURES") != "1",
    reason="native Ethernet management named-rail fixtures run in the pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_ethernet_management_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_ethernet_label import ethernet_label_fixture_lane
    from kicad_tooling.ci_hosted_support import HostedLog

    root = tmp_path
    log = HostedLog(root, f"native-ethernet-management-named-rail-{version}")
    ethernet_label_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        feature="management_named_rail",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("ethernet-management-named-rail-fixture/")
    }

    assert set(results) == {
        "ethernet-management-named-rail-fixture/native-export",
        "ethernet-management-named-rail-fixture/control",
        "ethernet-management-named-rail-fixture/fault",
    }
    fault = results["ethernet-management-named-rail-fixture/fault"]
    control = results["ethernet-management-named-rail-fixture/control"]
    assert fault["findings"] == "U1.5: MDC on return-like net GND"
    assert control["findings"] == "none"
    native_export = results["ethernet-management-named-rail-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
