"""Exact-version native fault/control coverage for an open CANH/CANL pin."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, can_unconnected_line_fixture_lane
from kicad_tooling.ci_hosted_can_unconnected_line import CAN_UNCONNECTED_LINE_TOOLCHAINS
from tests.native_fixture_support import assert_native_fixture_mounts

RULE_ID = "bus.can_unconnected_line"
TOOLCHAINS = tuple(
    pytest.param(version, image, id=f"kicad-{version}")
    for version, image in CAN_UNCONNECTED_LINE_TOOLCHAINS
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CAN_UNCONNECTED_LINE_FIXTURES") != "1",
    reason="native CAN unconnected-line fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
def test_native_can_unconnected_line_fault_and_control_repeat(
    tmp_path: Path, version: str, image: str
) -> None:
    log = HostedLog(tmp_path, f"native-can-unconnected-line-{version}")
    can_unconnected_line_fixture_lane(tmp_path, version=version, image=image, log=log)
    results = {
        item["stage"]: item
        for item in (
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        if item.get("stage", "").startswith("can-unconnected-line-fixture/")
    }

    assert set(results) == {
        "can-unconnected-line-fixture/native-export",
        "can-unconnected-line-fixture/control",
        "can-unconnected-line-fixture/fault",
    }
    native = results["can-unconnected-line-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert re.fullmatch(r"[0-9a-f]{64}", native["control_source_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", native["fault_source_sha256"])
    assert_native_fixture_mounts(tmp_path, native["command_receipt"])

    control = results["can-unconnected-line-fixture/control"]
    fault = results["can-unconnected-line-fixture/fault"]
    assert control["subjects"] == "none"
    assert fault["subjects"] == "U1.1: CANH"
    for result in (control, fault):
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", result["normalized_netlist_sha256"])
