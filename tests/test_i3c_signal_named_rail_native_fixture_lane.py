"""Exact-version native exports for I3C named-rail review fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i3c_signal_named_rail import (
    I3C_SIGNAL_NAMED_RAIL_TOOLCHAINS,
    i3c_signal_named_rail_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog

RULE_ID = "bus.i3c_signal_on_named_rail"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in I3C_SIGNAL_NAMED_RAIL_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I3C_SIGNAL_NAMED_RAIL_FIXTURES") != "1",
    reason="native I3C named-rail fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_i3c_signal_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    log = HostedLog(tmp_path, f"native-i3c-signal-named-rail-{version}")
    i3c_signal_named_rail_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("i3c-signal-named-rail-fixture/")
    }

    assert set(results) == {
        "i3c-signal-named-rail-fixture/native-export",
        "i3c-signal-named-rail-fixture/control",
        "i3c-signal-named-rail-fixture/fault",
    }
    fault = results["i3c-signal-named-rail-fixture/fault"]
    control = results["i3c-signal-named-rail-fixture/control"]
    assert fault["subjects"] == (
        "U1.1: I3C SDA on return-like net GND;U1.2: I3C SCL on supply-like net +3V3"
    )
    assert control["subjects"] == "none"
    assert fault["erc_errors"] == control["erc_errors"] == "none"
    native_export = results["i3c-signal-named-rail-fixture/native-export"]
    from tests.native_fixture_support import assert_native_fixture_mounts

    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
