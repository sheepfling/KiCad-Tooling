"""Exact-version native exports for I2S data-output sharing fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i2s_data_output_sharing import (
    I2S_DATA_OUTPUT_SHARING_TOOLCHAINS,
    i2s_data_output_sharing_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.i2s_data_outputs_share_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in I2S_DATA_OUTPUT_SHARING_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_I2S_DATA_OUTPUT_SHARING_FIXTURES") != "1",
    reason="I2S data-output fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_i2s_data_output_sharing_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:
    log = HostedLog(tmp_path, f"native-i2s-data-output-sharing-{version}")
    i2s_data_output_sharing_fixture_lane(
        tmp_path,
        version=version,
        image=image,
        log=log,
    )
    events = tuple(
        json.loads(line)
        for line in log.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    results = {
        item["stage"].rsplit("/", 1)[-1]: item
        for item in events
        if item.get("stage", "").startswith("i2s-data-output-sharing-same-net-fixture/")
        and item.get("stage")
        in {
            "i2s-data-output-sharing-same-net-fixture/native-export",
            "i2s-data-output-sharing-same-net-fixture/fault",
            "i2s-data-output-sharing-same-net-fixture/control",
        }
    }

    assert set(results) == {"native-export", "fault", "control"}
    assert_native_fixture_mounts(tmp_path, results["native-export"]["command_receipt"])
    fault = results["fault"]
    control = results["control"]
    assert fault["subjects"] == "U1, U2: I2S data-output pins share I2S_DATA_SHARED"
    assert control["subjects"] == "none"
    for item in (fault, control):
        assert item["status"] == "PASS"
        assert item["kicad_version"] == version
        assert item["image"] == image
        assert item["erc_errors"] == "none"
        assert item["repeatable"] == "true"
        assert item["normalized_netlist_sha256"] == item["repeat_normalized_netlist_sha256"]
