"""Exact-version native exports for serial endpoint-role fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_serial_endpoint_role_collision import (
    SERIAL_ENDPOINT_ROLE_COLLISION_TOOLCHAINS,
    serial_endpoint_role_collision_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in SERIAL_ENDPOINT_ROLE_COLLISION_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_SERIAL_ENDPOINT_ROLE_COLLISION_FIXTURES") != "1",
    reason="serial endpoint-role fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id="bus.serial_endpoint_role_collision")
def test_native_serial_endpoint_role_fault_and_crossed_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-serial-endpoint-role-{version}")
    serial_endpoint_role_collision_fixture_lane(tmp_path, version=version, image=image, log=log)
    prefix = "serial-endpoint-role-collision-fixture/"
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith(prefix)
    }
    assert set(results) == {f"{prefix}native-export", f"{prefix}control", f"{prefix}fault"}
    assert results[f"{prefix}fault"]["subjects"] == (
        "J1/U1: serial RX functions share UART_RX;J1/U1: serial TX functions share UART_TX"
    )
    assert results[f"{prefix}control"]["subjects"] == "none"
    assert_native_fixture_mounts(tmp_path, results[f"{prefix}native-export"]["command_receipt"])
    for case in ("fault", "control"):
        result = results[f"{prefix}{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
