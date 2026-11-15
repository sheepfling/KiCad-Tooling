"""Digest-pinned native exports for JTAG named-rail fault/control fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_jtag_signal_named_rail import (
    JTAG_SIGNAL_NAMED_RAIL_TOOLCHAINS,
    jtag_signal_named_rail_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.jtag_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in JTAG_SIGNAL_NAMED_RAIL_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_JTAG_SIGNAL_NAMED_RAIL_FIXTURES") != "1",
    reason="native JTAG named-rail fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_jtag_signal_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-jtag-signal-named-rail-{version}")
    jtag_signal_named_rail_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("jtag-signal-named-rail-fixture/")
    }

    assert set(results) == {
        "jtag-signal-named-rail-fixture/native-export",
        "jtag-signal-named-rail-fixture/control",
        "jtag-signal-named-rail-fixture/fault",
    }
    native_export = results["jtag-signal-named-rail-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert results["jtag-signal-named-rail-fixture/fault"]["subjects"] == (
        "U1.1: JTAG_TCK on return-like net GND;U1.3: JTAG_TDI on supply-like net +3V3"
    )
    assert results["jtag-signal-named-rail-fixture/control"]["subjects"] == "none"
    for case in ("fault", "control"):
        result = results[f"jtag-signal-named-rail-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
