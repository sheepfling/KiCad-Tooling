"""Exact-version native fixture checks for mapped SPI bias arrays."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_bias_arrays import (
    SPI_BIAS_ARRAY_TOOLCHAINS,
    spi_bias_array_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "bus.spi_active_low_chip_select_without_pullup"
PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SPI_BIAS_ARRAY_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_BIAS_ARRAY_FIXTURES") != "1",
    reason="SPI bias-array fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_spi_bias_array_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:

    log = HostedLog(tmp_path, f"native-spi-bias-array-{version}")
    spi_bias_array_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-bias-array-fixture/")
    }

    assert set(results) == {
        "spi-bias-array-fixture/native-export",
        "spi-bias-array-fixture/control",
        "spi-bias-array-fixture/fault",
        "spi-bias-array-fixture/no-connect",
    }
    native_export = results["spi-bias-array-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    control = results["spi-bias-array-fixture/control"]
    fault = results["spi-bias-array-fixture/fault"]
    no_connect = results["spi-bias-array-fixture/no-connect"]
    assert control["array_check_status"] == "PASS"
    assert control["finding_subjects"] == "none"
    assert fault["array_check_status"] == "FAIL"
    assert fault["finding_subjects"] == "SPI_CS_N: active-low SPI chip-select bias"
    assert no_connect["array_check_status"] == "PASS"
    assert no_connect["endpoint_check_status"] == "FAIL"
    assert no_connect["finding_subjects"] == "none"
    assert no_connect["explicit_unconnected_select"] == "U2.1"
    for result in (control, fault, no_connect):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["contract_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
    assert control["contract_sha256"] == fault["contract_sha256"] == no_connect["contract_sha256"]
