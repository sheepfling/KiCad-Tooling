"""Measure duplicate custom-property export behavior with pinned KiCad images."""

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
from kicad_tooling.hwrepo.schematic_conflicting_placed_custom_properties import (
    source_bound_conflicting_placed_custom_property_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.conflicting_placed_custom_properties"
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
FIXTURES = Path(__file__).parent / "fixtures/design_lint/conflicting-placed-custom-properties"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
CASES = (
    "fault",
    "control-unique",
    "control-identical-duplicates",
    "control-distinct-names",
    "control-case-distinct-names",
)
EXPECTED_FIELD_VALUE = {
    "10.0.0": "SYNTHETIC-PN-B",
    "10.0.5": "SYNTHETIC-PN-B",
    "10.0.8": "SYNTHETIC-PN-A",
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
) -> tuple[tuple[tuple[str, str | None], ...], tuple[str, ...]]:
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
        home_directory=f"conflicting-custom-property-{version}-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == f"Eeschema {version}"
    component = xml.find("./components/comp[@ref='J1']")
    assert component is not None
    fields = component.find("./fields")
    exported_fields = (
        ()
        if fields is None
        else tuple(
            (field.get("name", ""), field.text)
            for field in fields.findall("field")
            if field.get("name", "").casefold() in {"mfr_pn", "mfr_pn_alt"}
        )
    )

    source_root = tmp_path / f"{version}-{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=version),
    )
    candidates = source_bound_conflicting_placed_custom_property_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    values = tuple(
        value
        for item in candidates
        if item.rule_id == RULE_ID and item.evidence["property_name"] == ("MFR_PN",)
        for value in item.evidence["property_values"]
    )
    return exported_fields, values


@pytest.mark.parametrize("version", tuple(IMAGES))
def test_native_export_retains_one_version_dependent_custom_value_and_controls(
    tmp_path: Path,
    version: str,
) -> None:
    results = {case: _export_case(tmp_path, version, case, "first") for case in CASES}

    assert results["fault"] == (
        (("MFR_PN", EXPECTED_FIELD_VALUE[version]),),
        ("SYNTHETIC-PN-A", "SYNTHETIC-PN-B"),
    )
    assert results["control-unique"] == ((("MFR_PN", "SYNTHETIC-PN-A"),), ())
    assert results["control-identical-duplicates"] == ((("MFR_PN", "SYNTHETIC-PN-A"),), ())
    assert results["control-distinct-names"] == (
        (("MFR_PN", "SYNTHETIC-PN-A"), ("MFR_PN_ALT", "SYNTHETIC-PN-B")),
        (),
    )
    assert results["control-case-distinct-names"] == (
        (("MFR_PN", "SYNTHETIC-PN-A"), ("mfr_pn", "SYNTHETIC-PN-B")),
        (),
    )
    assert _export_case(tmp_path, version, "fault", "repeat") == results["fault"]
