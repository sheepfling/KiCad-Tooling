"""Exact-version native exports for the JTAG TCK/TMS same-net fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_jtag_clock_mode_same_net import (
    JTAG_CLOCK_MODE_SAME_NET_TOOLCHAINS,
    jtag_clock_mode_same_net_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.jtag_tck_tms_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in JTAG_CLOCK_MODE_SAME_NET_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_JTAG_CLOCK_MODE_SAME_NET_FIXTURES") != "1",
    reason="JTAG TCK/TMS fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_jtag_clock_mode_same_net_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:
    log = HostedLog(tmp_path, f"native-jtag-clock-mode-same-net-{version}")
    jtag_clock_mode_same_net_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
    )
    events = tuple(
        json.loads(line)
        for line in log.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    prefix = "jtag-tck-tms-same-net-fixture/"
    results = {
        item["stage"].rsplit("/", 1)[-1]: item
        for item in events
        if item.get("stage", "").startswith(prefix)
        and item.get("stage") in {f"{prefix}native-export", f"{prefix}fault", f"{prefix}control"}
    }

    assert set(results) == {"native-export", "fault", "control"}
    assert_native_fixture_mounts(tmp_path, results["native-export"]["command_receipt"])
    fault = results["fault"]
    control = results["control"]
    assert fault["subjects"] == ("U1: JTAG TCK U1.1 and TMS U1.2 share JTAG_CLOCK_MODE_SHARED")
    assert control["subjects"] == "none"
    for item in (fault, control):
        assert item["status"] == "PASS"
        assert item["kicad_version"] == version
        assert item["image"] == image
        assert item["erc_errors"] == "none"
        assert item["repeatable"] == "true"
        assert item["normalized_netlist_sha256"] == item["repeat_normalized_netlist_sha256"]
