"""Run exact-version native exports for synthetic I2C signal-label fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2c_signal_label import (
    I2C_NATIVE_TOOLCHAINS,
    i2c_signal_label_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i2c_signal_label_role_mismatch"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}") for version, image in I2C_NATIVE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2C_SIGNAL_LABEL_FIXTURES") != "1",
    reason="native I2C signal-label fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id="bus.i2c_signal_on_named_rail")
def test_native_i2c_signal_label_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    root = tmp_path
    log = HostedLog(root, f"native-i2c-signal-label-{version}")
    i2c_signal_label_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("i2c-signal-label-fixture/")
    }

    assert set(results) == {
        "i2c-signal-label-fixture/native-export",
        "i2c-signal-label-fixture/control",
        "i2c-signal-label-fixture/fault",
        "i2c-signal-label-fixture/rail_fault",
    }
    fault = results["i2c-signal-label-fixture/fault"]
    control = results["i2c-signal-label-fixture/control"]
    rail_fault = results["i2c-signal-label-fixture/rail_fault"]
    assert fault["role_findings"] == "U1.1: SDA on I2C_SCL;U1.2: SCL on I2C_SDA"
    assert control["role_findings"] == "none"
    assert control["rail_findings"] == "none"
    assert fault["rail_findings"] == "none"
    assert rail_fault["role_findings"] == "none"
    assert rail_fault["rail_findings"] == "U1.1: SDA on return-like net GND"
    native_export = results["i2c-signal-label-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control, rail_fault):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
