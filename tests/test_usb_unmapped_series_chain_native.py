"""Digest-pinned native KiCad acceptance for multi-stage USB chain review."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.usb_peer_reference_support import lint_report

RULE_ID = "bus.usb_unmapped_series_chain"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.0@sha256:"
    "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
)
FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint"
FAULT = FIXTURE_ROOT / "usb-series-chain-native/two-stage-fault.kicad_sch"
CONTROL = FIXTURE_ROOT / "usb-data-path-native/external-phy-series-control.kicad_sch"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") != "1",
        reason="native USB series-chain fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _export_netlist(tmp_path: Path, fixture: Path, repeat: int):
    output = tmp_path / "native-output"
    output.mkdir(exist_ok=True)
    netlist_path = output / f"usb-series-{fixture.stem}-{repeat}.netlist.xml"
    result = execute_kicad_cli(
        IMAGE,
        (
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "--output",
            str(netlist_path),
            str(fixture),
        ),
        tmp_path,
        home_directory=f"usb-series-{fixture.stem}-{repeat}",
        fixture_directory=FIXTURE_ROOT,
        output_directory=output,
    )
    assert result.error is None, result.model_dump_json(indent=2)
    assert result.returncode == 0, result.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == "Eeschema 10.0.0"
    return read_netlist(netlist_path)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_two_stage_usb_fixture_lane_is_repeatable(tmp_path: Path) -> None:
    assert digest(FAULT) == "d41707fc9e2392d6933f03ea66949a30082128cf508fabaab0a3b4aaf916c9a8"
    first = _export_netlist(tmp_path, FAULT, 1)
    second = _export_netlist(tmp_path, FAULT, 2)

    assert first == second
    assert {"R1", "R2", "R3", "R4"} <= set(first.components)
    report = lint_report(first, path_map=None)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["USB_D+_path"][1].startswith("R3 33R Device:R")
    assert finding.evidence["USB_D-_path"][1].startswith("R4 33R Device:R")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_one_stage_usb_fixture_is_a_quiet_control(tmp_path: Path) -> None:
    first = _export_netlist(tmp_path, CONTROL, 1)
    second = _export_netlist(tmp_path, CONTROL, 2)

    assert first == second
    assert not any(item.rule_id == RULE_ID for item in lint_report(first, path_map=None).findings)
