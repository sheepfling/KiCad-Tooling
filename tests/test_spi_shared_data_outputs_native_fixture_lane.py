"""Exact-version native exports for SPI shared-data review fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_shared_data_outputs import (
    SPI_SHARED_DATA_OUTPUT_TOOLCHAINS,
    spi_shared_data_output_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "bus.spi_data_outputs_share_net"
PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SPI_SHARED_DATA_OUTPUT_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_SHARED_DATA_OUTPUT_FIXTURES") != "1",
    reason="SPI shared-data fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_spi_shared_data_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    root = tmp_path
    log = HostedLog(root, f"native-spi-shared-data-{version}")
    spi_shared_data_output_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-shared-data-fixture/")
    }

    assert set(results) == {
        "spi-shared-data-fixture/native-export",
        "spi-shared-data-fixture/control",
        "spi-shared-data-fixture/fault",
    }
    native_export = results["spi-shared-data-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    fault = results["spi-shared-data-fixture/fault"]
    control = results["spi-shared-data-fixture/control"]
    assert fault["subjects"] == "U2, U3: SPI data-output pins share SPI_MISO"
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
