"""Exact-version native source-to-map coverage for I2C address rules."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2c_address_map import i2c_address_map_fixture_lane
from kicad_tooling.ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_support import HostedLog
from tests.design_lint_fixtures.i2c_addresses import address_map, responder
from tests.native_fixture_support import assert_native_fixture_mounts

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
    os.environ.get("KICAD_RUN_NATIVE_I2C_ADDRESS_MAP_FIXTURES") != "1",
    reason="native I2C address-map fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
def test_native_i2c_address_map_faults_and_controls_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    collision_specifications = {
        "fault": address_map(responder("U1"), responder("U2")),
        "control": address_map(responder("U1"), responder("U2", address=0x51)),
    }
    mismatch_specifications = {
        "fault": address_map(responder("U1"), responder("U2", address=0x50)),
        "control": address_map(responder("U1"), responder("U2", address=0x51)),
    }
    unmapped_specification = address_map(responder("U1"))
    log = HostedLog(tmp_path, f"native-i2c-address-map-{version}")
    i2c_address_map_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
        specifications=collision_specifications,
        mismatch_specifications=mismatch_specifications,
        unmapped_specification=unmapped_specification,
    )

    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("i2c-address-map/")
    }
    assert set(results) == {
        "i2c-address-map/native-export",
        "i2c-address-map/collision/control",
        "i2c-address-map/collision/fault",
        "i2c-address-map/strap-mismatch/control",
        "i2c-address-map/strap-mismatch/fault",
        "i2c-address-map/unmapped-responder/control",
        "i2c-address-map/unmapped-responder/fault",
    }

    native = results["i2c-address-map/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["repeatable"] == "true"
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])

    fault = results["i2c-address-map/collision/fault"]
    assert fault["status"] == "PASS"
    assert fault["findings"] == "MAIN: U1, U2 at 0x50"
    assert fault["address_coverage"] == "COMPLETE"
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]

    control = results["i2c-address-map/collision/control"]
    assert control["status"] == "PASS"
    assert control["findings"] == "none"
    assert control["address_coverage"] == "COMPLETE"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]

    mismatch = results["i2c-address-map/strap-mismatch/fault"]
    assert mismatch["status"] == "PASS"
    assert mismatch["findings"] == "U2 on MAIN: 0x51"
    assert mismatch["address_coverage"] == "COMPLETE"
    assert mismatch["source_sha256"] == control["source_sha256"]
    assert mismatch["normalized_netlist_sha256"] == control["normalized_netlist_sha256"]

    corrected = results["i2c-address-map/strap-mismatch/control"]
    assert corrected["status"] == "PASS"
    assert corrected["findings"] == "none"
    assert corrected["address_coverage"] == "COMPLETE"
    assert corrected["source_sha256"] == control["source_sha256"]
    assert corrected["normalized_netlist_sha256"] == control["normalized_netlist_sha256"]

    unmapped = results["i2c-address-map/unmapped-responder/fault"]
    assert unmapped["status"] == "PASS"
    assert unmapped["findings"] == "U2: I2C address-map coverage"
    assert unmapped["address_coverage"] == "COMPLETE"
    assert unmapped["source_sha256"] == control["source_sha256"]
    assert unmapped["normalized_netlist_sha256"] == control["normalized_netlist_sha256"]

    mapped = results["i2c-address-map/unmapped-responder/control"]
    assert mapped["status"] == "PASS"
    assert mapped["findings"] == "none"
    assert mapped["address_coverage"] == "COMPLETE"
    assert mapped["source_sha256"] == control["source_sha256"]
    assert mapped["normalized_netlist_sha256"] == control["normalized_netlist_sha256"]
