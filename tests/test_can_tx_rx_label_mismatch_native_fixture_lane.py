"""Exact-version native exports for CAN TX/RX label-direction review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.can_tx_rx_label_mismatch"
PROJECT_TOOLCHAINS = (
    pytest.param(
        "controller",
        "10.0.0",
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        id="controller-kicad-10.0.0",
    ),
    pytest.param(
        "raspberry-pi-status-led",
        "10.0.5",
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        id="raspberry-pi-status-led-kicad-10.0.5",
    ),
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_TX_RX_LABEL_MISMATCH_FIXTURES") != "1",
    reason="native CAN TX/RX label fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("project", "version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_can_tx_rx_label_fault_and_control_repeat(
    hosted_reference_root: Path, project: str, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_can_tx_rx_label_mismatch import (
        can_tx_rx_label_mismatch_fixture_lane,
    )

    root = hosted_reference_root
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-can-tx-rx-label-{project}")
    can_tx_rx_label_mismatch_fixture_lane(root, version=version, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("can-tx-rx-label-fixture/")
    }

    assert set(results) == {
        "can-tx-rx-label-fixture/native-export",
        "can-tx-rx-label-fixture/control",
        "can-tx-rx-label-fixture/fault",
    }
    for case, expected in (
        ("fault", "U1.1: CAN1_TX on CAN1_RX;U1.2: CAN1_RX on CAN1_TX"),
        ("control", "none"),
    ):
        result = results[f"can-tx-rx-label-fixture/{case}"]
        assert result["subjects"] == expected
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
    assert_native_fixture_mounts(
        root, results["can-tx-rx-label-fixture/native-export"]["command_receipt"]
    )
