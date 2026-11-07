"""Exact-version native exports for same-net Ethernet pair fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_ethernet_label import (
    ETHERNET_LABEL_NATIVE_TOOLCHAINS,
    ethernet_label_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.complementary_pair_assignment"
PROJECT_TOOLCHAINS = tuple(
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
    os.environ.get("KICAD_RUN_NATIVE_ETHERNET_DATA_SAME_NET_FIXTURES") != "1",
    reason="same-net Ethernet pair fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_ethernet_data_pair_same_net_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-ethernet-data-pair-same-net-{version}")
    ethernet_label_fixture_lane(
        tmp_path, version=version, image=image, log=log, feature="data_same_net"
    )
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("ethernet-data-pair-same-net-fixture/")
    }
    assert set(results) == {
        "ethernet-data-pair-same-net-fixture/native-export",
        "ethernet-data-pair-same-net-fixture/control",
        "ethernet-data-pair-same-net-fixture/fault",
    }
    native_export = results["ethernet-data-pair-same-net-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    fault = results["ethernet-data-pair-same-net-fixture/fault"]
    control = results["ethernet-data-pair-same-net-fixture/control"]
    assert fault["findings"] == "U1: Ethernet TX pair"
    assert control["findings"] == "none"
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
