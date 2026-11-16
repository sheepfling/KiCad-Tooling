"""Digest-pinned KiCad export for the USB one-sided series path heuristic."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.usb_peer_reference_support import lint_report

RULE_ID = "bus.usb_unmapped_asymmetric_series"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.0@sha256:"
    "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
)
FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint"
FAULT = FIXTURE_ROOT / "usb-asymmetric-series-native/one-sided-series.kicad_sch"
CONTROL = FIXTURE_ROOT / "usb-data-path-native/external-phy-series-control.kicad_sch"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") != "1",
        reason="native USB path fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _export_netlist(tmp_path: Path, fixture: Path, repeat: int):
    output = tmp_path / "native-output"
    output.mkdir(exist_ok=True)
    netlist_path = output / f"usb-asymmetric-{fixture.stem}-{repeat}.netlist.xml"
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
        home_directory=f"usb-asymmetric-{fixture.stem}-{repeat}",
        fixture_directory=FIXTURE_ROOT,
        output_directory=output,
    )
    assert result.error is None, result.model_dump_json(indent=2)
    assert result.returncode == 0, result.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == "Eeschema 10.0.0"
    return read_netlist(netlist_path)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_one_sided_series_path_emits_repeatable_review(tmp_path: Path) -> None:
    assert digest(FAULT) == "836f7e8aabcfd52d4b0c2d3589c822eeaedc4afe2898846db81626c136a8b8fc"
    first = _export_netlist(tmp_path, FAULT, 1)
    second = _export_netlist(tmp_path, FAULT, 2)

    assert first == second
    assert "R1" in first.components
    assert "R2" not in first.components
    assert any(set(pins) >= {"J1.2", "U1.2"} for pins in first.nets.values())
    finding = next(item for item in lint_report(first).findings if item.rule_id == RULE_ID)
    assert finding.evidence["USB_series_resistor_line"] == ("D+",)
    assert finding.evidence["USB_direct_line"] == ("D-",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_matching_two_resistor_paths_are_a_quiet_control(tmp_path: Path) -> None:
    first = _export_netlist(tmp_path, CONTROL, 1)
    second = _export_netlist(tmp_path, CONTROL, 2)

    assert first == second
    assert {"R1", "R2"} <= set(first.components)
    assert not any(item.rule_id == RULE_ID for item in lint_report(first).findings)
