"""Exact-version native exports for same-net SPI data input/output fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "bus.spi_data_input_output_same_net"
PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}") for version, image in SPI_NATIVE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_DATA_SAME_NET_FIXTURES") != "1",
    reason="SPI data same-net fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_spi_data_same_net_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:
    from kicad_tooling.ci_hosted_spi_data_same_net import spi_data_same_net_fixture_lane

    log = HostedLog(tmp_path, f"native-spi-data-same-net-{version}")
    spi_data_same_net_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-data-same-net-fixture/")
    }

    assert set(results) == {
        "spi-data-same-net-fixture/native-export",
        "spi-data-same-net-fixture/control",
        "spi-data-same-net-fixture/fault",
    }
    native_export = results["spi-data-same-net-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    fault = results["spi-data-same-net-fixture/fault"]
    control = results["spi-data-same-net-fixture/control"]
    assert fault["subjects"] == "U1: SPI data-role pins share SPI_DATA"
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
