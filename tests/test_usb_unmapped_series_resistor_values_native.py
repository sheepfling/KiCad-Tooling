"""Digest-pinned KiCad exports for USB series-resistor value review."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.usb_peer_reference_support import lint_report

RULE_ID = "bus.usb_unmapped_series_resistor_value_mismatch"
FIXTURE_DIR = Path(__file__).parent / "fixtures/design_lint/usb-series-value-mismatch-native"
FAULT = FIXTURE_DIR / "fault.kicad_sch"
CONTROL = FIXTURE_DIR / "control.kicad_sch"
NATIVE_IMAGES = (
    (
        "10.0.0",
        (
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
        ),
    ),
    (
        "10.0.5",
        (
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
        ),
    ),
)

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


def _export_netlist(image: str, version: str, fixture: Path, repeat: int, tmp_path: Path):
    output = tmp_path / f"native-output-{version}-{fixture.stem}"
    output.mkdir(exist_ok=True)
    netlist_path = output / f"usb-series-value-{repeat}.netlist.xml"
    result = execute_kicad_cli(
        image,
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
        home_directory=f"usb-series-value-{version}-{fixture.stem}-{repeat}",
        fixture_directory=FIXTURE_DIR,
        output_directory=output,
    )
    assert result.error is None, result.model_dump_json(indent=2)
    assert result.returncode == 0, result.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == f"Eeschema {version}"
    return read_netlist(netlist_path)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(("version", "image"), NATIVE_IMAGES)
def test_native_value_mismatch_fault_and_equal_value_control_repeat(
    version: str,
    image: str,
    tmp_path: Path,
) -> None:
    assert digest(FAULT) == "78b5d5f31b9d4b7f19c836e6182acb910367a2312826e01d46bb950d1c3fe9a2"
    assert digest(CONTROL) == "87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f"

    fault_first = _export_netlist(image, version, FAULT, 1, tmp_path)
    fault_second = _export_netlist(image, version, FAULT, 2, tmp_path)
    control_first = _export_netlist(image, version, CONTROL, 1, tmp_path)
    control_second = _export_netlist(image, version, CONTROL, 2, tmp_path)

    assert fault_first == fault_second
    assert control_first == control_second
    assert {"R1", "R2"} <= set(fault_first.components)
    finding = next(
        item for item in lint_report(fault_first, path_map=None).findings if item.rule_id == RULE_ID
    )
    assert finding.evidence["USB_D+_nominal_resistance_ohms"] == ("27",)
    assert finding.evidence["USB_D-_nominal_resistance_ohms"] == ("33",)
    assert not any(
        item.rule_id == RULE_ID for item in lint_report(control_first, path_map=None).findings
    )
