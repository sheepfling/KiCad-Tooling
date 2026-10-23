"""Exact-version native exports for serial TX-output sharing fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_serial_tx_output_sharing import (
    SERIAL_TX_OUTPUT_SHARING_TOOLCHAINS,
)
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.serial_tx_outputs_share_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SERIAL_TX_OUTPUT_SHARING_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_TX_OUTPUT_SHARING_FIXTURES") != "1",
    reason="serial TX-sharing fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_serial_tx_output_sharing_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_serial_tx_output_sharing import (
        serial_tx_output_sharing_fixture_lane,
    )
    from kicad_tooling.ci_hosted_support import HostedLog

    root = tmp_path
    log = HostedLog(root, f"native-serial-tx-sharing-{version}")
    serial_tx_output_sharing_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("serial-tx-output-sharing-fixture/")
    }

    assert set(results) == {
        "serial-tx-output-sharing-fixture/native-export",
        "serial-tx-output-sharing-fixture/control",
        "serial-tx-output-sharing-fixture/fault",
    }
    native_export = results["serial-tx-output-sharing-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    control = results["serial-tx-output-sharing-fixture/control"]
    fault = results["serial-tx-output-sharing-fixture/fault"]
    assert control["subjects"] == "none"
    assert fault["subjects"] == "U1, U2: serial TX functions share SERIAL_TX_BUS"
    for result in (control, fault):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
