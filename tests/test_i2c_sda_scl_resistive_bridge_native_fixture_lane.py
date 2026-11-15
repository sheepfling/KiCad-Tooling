"""Exact-version native exports for the I2C SDA/SCL resistor bridge heuristic."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2c_sda_scl_resistive_bridge import (
    I2C_SDA_SCL_RESISTIVE_BRIDGE_TOOLCHAINS,
    i2c_sda_scl_resistive_bridge_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i2c_sda_scl_resistive_bridge"
FIXTURE_PREFIXES = (
    "i2c-sda-scl-resistive-bridge-fixture/",
    "i2c-sda-scl-connector-resistive-bridge-fixture/",
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in I2C_SDA_SCL_RESISTIVE_BRIDGE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2C_SDA_SCL_RESISTIVE_BRIDGE_FIXTURES") != "1",
    reason="native I2C resistor bridge fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_i2c_sda_scl_resistor_bridge_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-i2c-sda-scl-resistive-bridge-{version}")
    i2c_sda_scl_resistive_bridge_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith(FIXTURE_PREFIXES)
    }

    fixture_expectations = (
        (
            "i2c-sda-scl-resistive-bridge-fixture",
            "U1: I2C SDA/SCL nets I2C_SDA and I2C_SCL are bridged by R1",
        ),
        (
            "i2c-sda-scl-connector-resistive-bridge-fixture",
            "J1: I2C SDA/SCL nets I2C_SDA and I2C_SCL are bridged by R1",
        ),
    )
    expected_stages = {
        f"{prefix}/{stage}"
        for prefix, _fault_subject in fixture_expectations
        for stage in ("native-export", "control", "fault")
    }
    assert set(results) == expected_stages
    for prefix, fault_subject in fixture_expectations:
        native_export = results[f"{prefix}/native-export"]
        assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
        assert results[f"{prefix}/fault"]["subjects"] == fault_subject
        assert results[f"{prefix}/control"]["subjects"] == "none"
        for case in ("fault", "control"):
            result = results[f"{prefix}/{case}"]
            assert result["status"] == "PASS"
            assert result["kicad_version"] == version
            assert result["image"] == image
            assert result["erc_errors"] == "none"
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
            assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
