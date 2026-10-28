"""Run exact-version native exports for serial TX/RX label fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_serial_tx_rx_label_mismatch import (
    SERIAL_TX_RX_LABEL_TOOLCHAINS,
    serial_tx_rx_label_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.serial_tx_rx_label_mismatch"
NAMED_RAIL_RULE_ID = "bus.serial_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SERIAL_TX_RX_LABEL_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES") != "1",
    reason="native serial TX/RX label fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=NAMED_RAIL_RULE_ID)
def test_native_serial_tx_rx_label_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:

    root = tmp_path
    log = HostedLog(root, f"native-serial-tx-rx-label-{version}")
    serial_tx_rx_label_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("serial-tx-rx-label-fixture/")
    }

    assert set(results) == {
        "serial-tx-rx-label-fixture/native-export",
        "serial-tx-rx-label-fixture/control",
        "serial-tx-rx-label-fixture/fault",
        "serial-tx-rx-label-fixture/rail_fault",
    }
    fault = results["serial-tx-rx-label-fixture/fault"]
    control = results["serial-tx-rx-label-fixture/control"]
    rail_fault = results["serial-tx-rx-label-fixture/rail_fault"]
    assert fault["subjects"] == "U1.1: USART1_TX on USART1_RX;U1.2: USART1_RX on USART1_TX"
    assert control["subjects"] == "none"
    assert rail_fault["subjects"] == "none"
    assert rail_fault["rail_subjects"] == "U1.1: USART1_TX on return-like net GND"
    assert rail_fault["lint_status"] == "REVIEW"
    native_export = results["serial-tx-rx-label-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control, rail_fault):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
