"""Run exact-version native exports for SPI clock/select label fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_spi_clock_select_label_mismatch import (
    SPI_CLOCK_SELECT_LABEL_TOOLCHAINS,
    spi_clock_select_label_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.spi_clock_select_label_mismatch"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SPI_CLOCK_SELECT_LABEL_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SPI_CLOCK_SELECT_LABEL_FIXTURES") != "1",
    reason="native SPI clock/select label fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_spi_clock_select_label_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    root = tmp_path
    log = HostedLog(root, f"native-spi-clock-select-label-{version}")
    spi_clock_select_label_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("spi-clock-select-label-fixture/")
    }

    assert set(results) == {
        "spi-clock-select-label-fixture/native-export",
        "spi-clock-select-label-fixture/control",
        "spi-clock-select-label-fixture/fault",
    }
    fault = results["spi-clock-select-label-fixture/fault"]
    control = results["spi-clock-select-label-fixture/control"]
    assert fault["subjects"] == "U1.1: SPI1_SCK on SPI1_CS;U1.2: SPI1_NSS on SPI1_SCK"
    assert control["subjects"] == "none"
    native_export = results["spi-clock-select-label-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
