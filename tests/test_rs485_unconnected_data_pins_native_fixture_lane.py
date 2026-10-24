"""Run exact-version native exports for open RS-485 data-pin fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    HostedLog,
    rs485_unconnected_data_pin_fixture_lane,
)
from kicad_tooling.ci_hosted_rs485_unconnected_data import (
    RS485_UNCONNECTED_DATA_TOOLCHAINS,
)
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.rs485_unconnected_data_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in RS485_UNCONNECTED_DATA_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_RS485_UNCONNECTED_DATA_PIN_FIXTURES") != "1",
    reason="native RS-485 open-data fixtures run in digest-pinned acceptance",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
def test_native_open_rs485_data_pin_fault_and_connected_control(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-rs485-open-data-{version}")
    rs485_unconnected_data_pin_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("rs485-unconnected-data-fixture/")
    }

    assert set(results) == {
        "rs485-unconnected-data-fixture/native-export",
        "rs485-unconnected-data-fixture/control",
        "rs485-unconnected-data-fixture/fault",
    }
    fault = results["rs485-unconnected-data-fixture/fault"]
    control = results["rs485-unconnected-data-fixture/control"]
    native_export = results["rs485-unconnected-data-fixture/native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    assert fault["review_subjects"] == "U1.2: R"
    assert control["review_subjects"] == "none"
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["default_mode"] == "off"
        assert result["repeatable"] == "true"
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
