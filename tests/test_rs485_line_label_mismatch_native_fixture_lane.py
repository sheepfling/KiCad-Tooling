"""Exact-version native exports for RS-485 A/B line-label mismatch fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_rs485_data_same_net import (
    RS485_DATA_SAME_NET_TOOLCHAINS,
    rs485_line_label_mismatch_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.rs485_line_label_mismatch"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in RS485_DATA_SAME_NET_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_RS485_LINE_LABEL_MISMATCH_FIXTURES") != "1",
    reason="native RS-485 line-label fixtures run in the pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_rs485_line_label_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-rs485-line-label-mismatch-{version}")
    rs485_line_label_mismatch_fixture_lane(tmp_path, version=version, image=image, log=log)
    prefix = "rs485-line-label-mismatch-fixture/"
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith(prefix)
    }

    assert set(results) == {
        f"{prefix}native-export",
        f"{prefix}control",
        f"{prefix}fault",
    }
    fault = results[f"{prefix}fault"]
    control = results[f"{prefix}control"]
    assert fault["subjects"] == (
        "U1.1: RS-485 A function on RS485_B; U1.2: RS-485 B function on RS485_A"
    )
    assert control["subjects"] == "none"
    assert fault["erc_errors"] == control["erc_errors"] == "none"
    native_export = results[f"{prefix}native-export"]
    assert_native_fixture_mounts(tmp_path, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
