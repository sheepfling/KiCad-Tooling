"""Exact-version KiCad coverage for open SPI data-function pins."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id="bus.spi_unconnected_data_pin"),
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}") for version, image in SPI_NATIVE_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_UNCONNECTED_DATA_FIXTURES") != "1",
    reason="native SPI open-data fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
def test_native_open_spi_data_pin_fault_and_connected_control(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, spi_unconnected_data_fixture_lane

    log = HostedLog(tmp_path, f"native-spi-unconnected-data-{version}")
    spi_unconnected_data_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-unconnected-data-fixture/")
    }
    assert set(results) == {
        "spi-unconnected-data-fixture/native-export",
        "spi-unconnected-data-fixture/control",
        "spi-unconnected-data-fixture/fault",
    }

    native = results["spi-unconnected-data-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["control_source_sha256"] == (
        "af3490ef9bd15a32ec307a50c807a56611ca3f2e6e597bc66368b4fdadc97a2a"
    )
    assert native["fault_source_sha256"] == (
        "d18786cbb35cf58f723b452b12b61abe5b3f347ebc1a540e3b9655097e98f13d"
    )
    assert native["repeatable"] == "true"
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])

    control = results["spi-unconnected-data-fixture/control"]
    assert control["status"] == "PASS"
    assert control["findings"] == "none"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]

    fault = results["spi-unconnected-data-fixture/fault"]
    assert fault["status"] == "PASS"
    assert fault["default_mode"] == "off"
    assert fault["default_disposition"] == "RULE_OFF"
    assert fault["review_mode"] == "review"
    assert fault["review_disposition"] == "OPEN"
    assert fault["findings"] == "U1.1: MOSI"
    assert "spi_data_family=MOSI-family" in fault["evidence"]
    assert "spi_channel=default" in fault["evidence"]
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
