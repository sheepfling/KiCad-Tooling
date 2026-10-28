"""Exact-version native fixtures for shared SPI chip-select review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_shared_chip_select import (
    SPI_SHARED_CHIP_SELECT_TOOLCHAINS,
    spi_shared_chip_select_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "bus.spi_chip_select_inputs_share_net"
PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SPI_SHARED_CHIP_SELECT_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_SHARED_CHIP_SELECT_FIXTURES") != "1",
    reason="SPI shared-select fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_spi_shared_chip_select_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    log = HostedLog(tmp_path, f"native-spi-shared-chip-select-{version}")
    spi_shared_chip_select_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-shared-chip-select-fixture/")
    }

    assert set(results) == {
        "spi-shared-chip-select-fixture/native-export",
        "spi-shared-chip-select-fixture/fault",
        "spi-shared-chip-select-fixture/control",
    }
    native_export = results["spi-shared-chip-select-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    fault = results["spi-shared-chip-select-fixture/fault"]
    control = results["spi-shared-chip-select-fixture/control"]
    assert fault["subjects"] == "U2, U3: SPI chip-select inputs share SPI_CS0"
    assert control["subjects"] == "none"
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
