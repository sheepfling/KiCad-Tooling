"""Exact KiCad-version regressions for the SPI open-clock review rule."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.spi_unconnected_clock_pin"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_UNCONNECTED_CLOCK_FIXTURES") != "1",
    reason="native SPI open-clock fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("version", "image"),
    tuple(
        pytest.param(version, image, id=f"kicad-{version}")
        for version, image in SPI_NATIVE_TOOLCHAINS
    ),
)
def test_native_open_spi_clock_fault_and_connected_control(
    tmp_path: Path, version: str, image: str
) -> None:
    import json

    from kicad_tooling.ci_hosted import HostedLog, spi_unconnected_clock_fixture_lane

    log = HostedLog(tmp_path, f"native-spi-unconnected-clock-{version}")
    spi_unconnected_clock_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-unconnected-clock-fixture/")
    }
    assert set(results) == {
        "spi-unconnected-clock-fixture/native-export",
        "spi-unconnected-clock-fixture/control",
        "spi-unconnected-clock-fixture/fault",
    }
    native = results["spi-unconnected-clock-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])
    control = results["spi-unconnected-clock-fixture/control"]
    assert control["subjects"] == "none"
    fault = results["spi-unconnected-clock-fixture/fault"]
    assert fault["subjects"] == "U1.1: SCK"
    assert fault["repeatable"] == "true"
    assert control["repeatable"] == fault["repeatable"] == "true"
