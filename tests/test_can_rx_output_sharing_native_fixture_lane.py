"""Exact-version native exports for CAN receiver-output sharing fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_can_rx_output_sharing import (
    CAN_RX_OUTPUT_SHARING_TOOLCHAINS,
    can_rx_output_sharing_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog

RULE_ID = "bus.can_rx_outputs_share_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in CAN_RX_OUTPUT_SHARING_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_RX_OUTPUT_SHARING_FIXTURES") != "1",
    reason="CAN RX-sharing fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_can_rx_output_sharing_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-can-rx-output-sharing-{version}")
    can_rx_output_sharing_fixture_lane(tmp_path, version=version, image=image, log=log)
    events = [
        json.loads(line)
        for line in log.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fixtures = {
        item["stage"].rsplit("/", 1)[-1]: item
        for item in events
        if item.get("stage", "").startswith("can-rx-output-sharing-fixture/")
        and item.get("stage")
        in {
            "can-rx-output-sharing-fixture/fault",
            "can-rx-output-sharing-fixture/control",
        }
    }

    assert set(fixtures) == {"fault", "control"}
    assert all(item["status"] == "PASS" for item in fixtures.values())
    assert all(item["kicad_version"] == version for item in fixtures.values())
    assert all(item["repeatable"] == "true" for item in fixtures.values())
