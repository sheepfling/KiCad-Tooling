"""Exact-version native acceptance for a one-sided open I3C signal pair."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, i3c_unconnected_pin_fixture_lane
from kicad_tooling.ci_hosted_i3c_unconnected_pin import I3C_UNCONNECTED_PIN_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i3c_unconnected_pin"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in I3C_UNCONNECTED_PIN_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I3C_UNCONNECTED_PIN_FIXTURES") != "1",
    reason="native I3C open-pin fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_i3c_unconnected_pin_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-i3c-unconnected-pin-{version}")
    i3c_unconnected_pin_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("i3c-unconnected-pin-fixture/")
    }
    assert set(results) == {
        "i3c-unconnected-pin-fixture/native-export",
        "i3c-unconnected-pin-fixture/control",
        "i3c-unconnected-pin-fixture/fault",
    }
    native = results["i3c-unconnected-pin-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])
    assert results["i3c-unconnected-pin-fixture/control"]["subjects"] == "none"
    fault = results["i3c-unconnected-pin-fixture/fault"]
    assert fault["subjects"] == "U1.2: I3C1_SCL"
    assert fault["erc_errors"] == "none"
    for case in ("control", "fault"):
        result = results[f"i3c-unconnected-pin-fixture/{case}"]
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
