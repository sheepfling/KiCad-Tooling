"""Exact-version native exports for I2C responder-address collision fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2c_address_collision import i2c_address_collision_fixture_lane
from kicad_tooling.ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_support import HostedLog
from tests.design_lint_fixtures.i2c_addresses import address_map, responder
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i2c_address_collision"
NATIVE_FIXTURE = "KICAD_RUN_NATIVE_I2C_ADDRESS_COLLISION_FIXTURES"

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
    os.environ.get(NATIVE_FIXTURE) != "1",
    reason="native I2C address fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_i2c_address_collision_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    specifications = {
        "fault": address_map(responder("U1"), responder("U2")),
        "control": address_map(responder("U1"), responder("U2", address=0x51)),
    }
    log = HostedLog(tmp_path, f"native-i2c-address-collision-{version}")
    i2c_address_collision_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
        specifications=specifications,
    )

    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("i2c-address-collision-fixture/")
    }
    assert set(results) == {
        "i2c-address-collision-fixture/native-export",
        "i2c-address-collision-fixture/control",
        "i2c-address-collision-fixture/fault",
    }

    native = results["i2c-address-collision-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["repeatable"] == "true"
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])

    fault = results["i2c-address-collision-fixture/fault"]
    assert fault["status"] == "PASS"
    assert fault["findings"] == "MAIN: U1, U2 at 0x50"
    assert fault["address_coverage"] == "COMPLETE"
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]

    control = results["i2c-address-collision-fixture/control"]
    assert control["status"] == "PASS"
    assert control["findings"] == "none"
    assert control["address_coverage"] == "COMPLETE"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
