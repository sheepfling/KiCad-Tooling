"""Exact-version native exports for shared RS-485 receiver-output fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_rs485_receiver_output_sharing import (
    RS485_RECEIVER_OUTPUT_TOOLCHAINS,
    rs485_receiver_output_sharing_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.rs485_receiver_outputs_share_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in RS485_RECEIVER_OUTPUT_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_RS485_RECEIVER_OUTPUT_SHARING_FIXTURES") != "1",
    reason="native RS-485 receiver-output fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_shared_receiver_output_fault_and_separate_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    root = tmp_path
    log = HostedLog(root, f"native-rs485-receiver-output-{version}")
    rs485_receiver_output_sharing_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("rs485-receiver-output-fixture/")
    }

    assert set(results) == {
        "rs485-receiver-output-fixture/native-export",
        "rs485-receiver-output-fixture/control",
        "rs485-receiver-output-fixture/fault",
    }
    native_export = results["rs485-receiver-output-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    fault = results["rs485-receiver-output-fixture/fault"]
    control = results["rs485-receiver-output-fixture/control"]
    assert fault["subjects"] == "U1, U2: RS-485 receiver-output pins share RX_SHARED"
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
