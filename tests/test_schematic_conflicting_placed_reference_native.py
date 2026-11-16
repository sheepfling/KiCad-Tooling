"""Measure conflicting placed Reference fields with pinned native KiCad exports."""

from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_conflicting_placed_reference import (
    source_bound_conflicting_placed_reference_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.conflicting_placed_reference_properties"
IMAGES = {
    "10.0.0": (
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
    ),
    "10.0.5": (
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
    ),
    "10.0.8": (
        "ghcr.io/kicad/kicad:10.0.8@sha256:"
        "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
    ),
}
FIXTURES = Path(__file__).parent / "fixtures/design_lint/conflicting-placed-reference"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
CASES = {
    "fault": True,
    "control": False,
    "control-duplicate-same-reference": False,
    "control-library-only-conflict": False,
}
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_SYMBOL_INTEGRITY_FIXTURES") != "1",
        reason="native schematic source-integrity fixtures run in the pinned acceptance lane",
    ),
]


def _export_case(
    tmp_path: Path,
    version: str,
    case: str,
    repeat: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    output = tmp_path / "native-output"
    output.mkdir(exist_ok=True)
    netlist_path = output / f"{version}-{case}-{repeat}.netlist.xml"
    command = execute_kicad_cli(
        IMAGES[version],
        (
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "--output",
            str(netlist_path),
            str(FIXTURES / f"{case}.kicad_sch"),
        ),
        tmp_path,
        home_directory=f"conflicting-reference-{version}-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == f"Eeschema {version}"
    component = xml.find("./components/comp[@ref='J1']")
    assert component is not None
    assert component.findall("./property[@name='Reference']") == []
    references = tuple(sorted(item.get("ref", "") for item in xml.findall("./components/comp")))

    source_root = tmp_path / f"{version}-{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=version),
    )
    candidates = source_bound_conflicting_placed_reference_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    property_values = tuple(
        value
        for item in candidates
        if item.rule_id == RULE_ID
        for value in item.evidence["property_values"]
    )
    return references, property_values, tuple(item.subject for item in candidates)


@pytest.mark.parametrize("version", tuple(IMAGES))
def test_native_exports_hide_conflicting_reference_fields_and_controls_stay_quiet(
    tmp_path: Path,
    version: str,
) -> None:
    results = {case: _export_case(tmp_path, version, case, "first") for case in CASES}

    for case, expected_finding in CASES.items():
        references, property_values, subjects = results[case]
        assert references == ("J1", "U1")
        assert property_values == (("J1", "J9") if expected_finding else ())
        assert bool(subjects) is expected_finding

    assert _export_case(tmp_path, version, "fault", "repeat") == results["fault"]
