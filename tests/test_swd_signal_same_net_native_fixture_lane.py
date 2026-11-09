"""Exact-version native exports for SWDIO/SWCLK same-net fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_swdio_swclk_same_net import (
    SWD_SIGNAL_SAME_NET_TOOLCHAINS,
    swdio_swclk_same_net_fixture_lane,
)
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.swdio_swclk_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SWD_SIGNAL_SAME_NET_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SWD_SIGNAL_SAME_NET_FIXTURES") != "1",
    reason="native SWD same-net fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_swdio_swclk_same_net_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-swd-signal-same-net-{version}")
    swdio_swclk_same_net_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("swd-swdio-swclk-same-net-fixture/")
    }

    assert set(results) == {
        "swd-swdio-swclk-same-net-fixture/native-export",
        "swd-swdio-swclk-same-net-fixture/control",
        "swd-swdio-swclk-same-net-fixture/fault",
    }
    native_export = results["swd-swdio-swclk-same-net-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert results["swd-swdio-swclk-same-net-fixture/fault"]["subjects"] == (
        "U1: SWDIO U1.5 and SWCLK U1.6 share SWD_SHARED"
    )
    assert results["swd-swdio-swclk-same-net-fixture/control"]["subjects"] == "none"
    for case in ("fault", "control"):
        result = results[f"swd-swdio-swclk-same-net-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
