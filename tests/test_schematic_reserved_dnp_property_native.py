"""Measure DNP-property collisions against pinned KiCad 10 native exporters."""

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
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.schematic_reserved_dnp_property import (
    source_bound_reserved_dnp_property_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.reserved_dnp_property_collision"
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
FIXTURES = Path(__file__).parent / "fixtures/design_lint/reserved-dnp-property"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
CASES = {
    "fault-custom-only-yes": ((), True),
    "fault-native-yes-custom-no": (("J1",), True),
    "control-native-dnp": (("J1",), False),
    "control-library-only": ((), False),
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
) -> tuple[tuple[str, ...], bool, tuple[str, ...]]:
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
        home_directory=f"reserved-dnp-{version}-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    xml = netlist_path.read_text(encoding="utf-8")
    assert f"<tool>Eeschema {version}</tool>" in xml
    component = ET.parse(netlist_path).find("./components/comp[@ref='J1']")
    assert component is not None
    custom_dnp_fields = component.findall("./fields/field[@name='dnp']")
    if case == "fault-custom-only-yes":
        assert [field.text for field in custom_dnp_fields] == ["yes"]
    elif case == "fault-native-yes-custom-no":
        assert [field.text for field in custom_dnp_fields] == ["no"]

    contract = read_netlist(netlist_path)
    source_root = tmp_path / f"{version}-{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=version),
    )
    candidates = source_bound_reserved_dnp_property_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    return (
        contract.dnp_components,
        any(item.rule_id == RULE_ID for item in candidates),
        tuple(item.subject for item in candidates),
    )


@pytest.mark.parametrize("version", tuple(IMAGES))
def test_native_exports_preserve_population_and_review_reserved_fields(
    tmp_path: Path,
    version: str,
) -> None:
    results = {case: _export_case(tmp_path, version, case, "first") for case in CASES}

    for case, (expected_dnp, expected_finding) in CASES.items():
        dnp_components, found, subjects = results[case]
        assert dnp_components == expected_dnp
        assert found is expected_finding
        assert bool(subjects) is expected_finding

    repeated_fault = _export_case(tmp_path, version, "fault-custom-only-yes", "repeat")
    assert repeated_fault == results["fault-custom-only-yes"]
