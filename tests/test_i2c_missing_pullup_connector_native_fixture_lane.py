"""Exact-version native exports for connector-only I2C pull-up review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2c_missing_pullup_connector import (
    i2c_missing_pullup_connector_fixture_lane,
)
from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i2c_missing_pullup"
FIXTURE_PREFIX = "i2c-missing-pullup-connector-fixture/"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in KICAD_10_NATIVE_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2C_MISSING_PULLUP_CONNECTOR_FIXTURES") != "1",
    reason="connector-only I2C pull-up fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_connector_only_i2c_missing_pullup_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-i2c-missing-pullup-connector-{version}")
    i2c_missing_pullup_connector_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
    )
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith(FIXTURE_PREFIX)
    }

    assert set(results) == {
        f"{FIXTURE_PREFIX}native-export",
        f"{FIXTURE_PREFIX}control",
        f"{FIXTURE_PREFIX}fault",
    }
    native = results[f"{FIXTURE_PREFIX}native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])
    assert results[f"{FIXTURE_PREFIX}fault"]["subjects"] == "SDA I2C_SDA / SCL I2C_SCL"
    assert results[f"{FIXTURE_PREFIX}control"]["subjects"] == "none"
    for case in ("control", "fault"):
        result = results[f"{FIXTURE_PREFIX}{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
