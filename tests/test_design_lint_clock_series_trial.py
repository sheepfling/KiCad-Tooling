"""Keep native clock-series cohort fixtures reproducible and synthetic."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.design_lint_fixtures.clock_series_trial import _PIN_LIBRARY, CASES, render_case

FIXTURES = Path(__file__).parent / "fixtures" / "design_lint" / "cohort-clock-series-native"


@pytest.mark.parametrize("case_name,case", CASES.items(), ids=CASES)
def test_clock_series_trial_fixture_matches_its_generator(case_name, case) -> None:
    source = FIXTURES / f"{case_name}.kicad_sch"

    assert source.is_file()
    assert source.read_text(encoding="utf-8") == render_case(case_name, case)


def test_clock_series_trial_expectations_match_generator() -> None:
    expectations = json.loads((FIXTURES / "expectations.json").read_text(encoding="utf-8"))

    assert expectations == {
        "schema_version": 1,
        "cases": {
            name: {
                "candidate_finding": case.candidate_finding,
                "disposition": case.disposition,
            }
            for name, case in CASES.items()
        },
    }


@pytest.mark.native_kicad
@pytest.mark.parametrize("case_name,case", CASES.items(), ids=CASES)
def test_clock_series_trial_fixture_matches_native_netlist_and_erc(
    case_name, case, native_schematic_geometry_toolchain, tmp_path
) -> None:
    cli, _version = native_schematic_geometry_toolchain
    source = FIXTURES / f"{case_name}.kicad_sch"
    netlist_path = tmp_path / "netlist.xml"
    erc_path = tmp_path / "erc.json"

    netlist_result = subprocess.run(
        (
            str(cli),
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "--output",
            str(netlist_path),
            str(source),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert netlist_result.returncode == 0, netlist_result.stderr

    erc_result = subprocess.run(
        (
            str(cli),
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            str(erc_path),
            str(source),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert erc_result.returncode == 0, erc_result.stderr

    root = ET.parse(netlist_path).getroot()
    observed = {
        (node.get("ref", ""), node.get("pin", "")): net.get("name", "").lstrip("/")
        for net in root.findall("./nets/net")
        for node in net.findall("node")
    }
    expected = {
        (part.reference, pin.number): net
        for part in case.parts
        for pin, net in zip(_PIN_LIBRARY[part.library_id], part.pin_nets, strict=True)
    }
    assert observed == expected

    erc = json.loads(erc_path.read_text(encoding="utf-8"))
    errors = [
        violation
        for sheet in erc.get("sheets", [])
        for violation in sheet.get("violations", [])
        if violation.get("severity") == "error"
    ]
    assert not errors
