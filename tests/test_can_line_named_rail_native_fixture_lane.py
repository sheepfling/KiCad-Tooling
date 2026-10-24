"""Exact-version native exports for CAN line named-rail review fixtures."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_can_signal_named_rail import CAN_SIGNAL_NAMED_RAIL_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.can_line_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

PROJECT_TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in CAN_SIGNAL_NAMED_RAIL_TOOLCHAINS
)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_LINE_NAMED_RAIL_FIXTURES") != "1",
    reason="native CAN line named-rail fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), PROJECT_TOOLCHAINS)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_can_line_named_rail_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    from kicad_tooling.ci_hosted_can_signal_named_rail import can_line_named_rail_fixture_lane
    from kicad_tooling.ci_hosted_support import HostedLog

    root = tmp_path
    log = HostedLog(root, f"native-can-line-named-rail-{version}")
    can_line_named_rail_fixture_lane(root, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("can-line-named-rail-fixture/")
    }

    assert set(results) == {
        "can-line-named-rail-fixture/native-export",
        "can-line-named-rail-fixture/control",
        "can-line-named-rail-fixture/fault",
    }
    fault = results["can-line-named-rail-fixture/fault"]
    control = results["can-line-named-rail-fixture/control"]
    assert fault["subjects"] == (
        "U1.1: CANH on return-like net GND;U1.2: CANL on supply-like net +3V3"
    )
    assert control["subjects"] == "none"
    assert fault["lint_status"] == "REVIEW"
    native_export = results["can-line-named-rail-fixture/native-export"]
    assert_native_fixture_mounts(root, native_export["command_receipt"])
    for result in (fault, control):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
