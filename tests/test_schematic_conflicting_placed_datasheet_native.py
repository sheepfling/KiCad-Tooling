"""Measure conflicting placed Datasheet fields with pinned native exports."""

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
from kicad_tooling.hwrepo.schematic_conflicting_placed_datasheet import (
    source_bound_conflicting_placed_datasheet_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.conflicting_placed_datasheet_properties"
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
FIXTURES = Path(__file__).parent / "fixtures/design_lint/conflicting-placed-datasheet"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
CASES = {
    "fault": (("https://example.invalid/first", "https://example.invalid/second"), True),
    "control": (("https://example.invalid/first",), False),
    "control-duplicate-same-datasheet": (
        ("https://example.invalid/first", "https://example.invalid/first"),
        False,
    ),
    "control-library-only-conflict": ((), False),
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
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
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
        home_directory=f"conflicting-datasheet-{version}-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    xml = ET.parse(netlist_path).getroot()
    assert xml.findtext("./design/tool") == f"Eeschema {version}"
    component = xml.find("./components/comp[@ref='J1']")
    assert component is not None
    datasheet = component.find("./fields/field[@name='Datasheet']")
    exported_datasheet = None if datasheet is None else datasheet.text

    source_root = tmp_path / f"{version}-{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=version),
    )
    candidates = source_bound_conflicting_placed_datasheet_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    values = tuple(
        value
        for item in candidates
        if item.rule_id == RULE_ID
        for value in item.evidence["datasheet_values"]
    )
    return exported_datasheet, values, tuple(item.subject for item in candidates)


@pytest.mark.parametrize("version", tuple(IMAGES))
def test_native_exports_keep_only_the_later_conflicting_datasheet_value(
    tmp_path: Path,
    version: str,
) -> None:
    results = {case: _export_case(tmp_path, version, case, "first") for case in CASES}

    for case, (expected_values, expected_finding) in CASES.items():
        exported_datasheet, values, subjects = results[case]
        assert values == (expected_values if expected_finding else ())
        assert bool(subjects) is expected_finding
        if expected_values:
            assert exported_datasheet == expected_values[-1]
        else:
            assert exported_datasheet in {None, ""}

    assert _export_case(tmp_path, version, "fault", "repeat") == results["fault"]
