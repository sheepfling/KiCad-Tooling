"""Exact KiCad proof that a missing embedded symbol can disappear from netlist output."""

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
from kicad_tooling.hwrepo.schematic_source_integrity import (
    missing_embedded_library_symbol_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.missing_embedded_symbol_definition"
VERSION = "10.0.5"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.5@sha256:"
    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
)
FIXTURES = Path(__file__).parent / "fixtures/design_lint/missing-embedded-symbol-definition"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_SYMBOL_INTEGRITY_FIXTURES") != "1",
        reason="native missing-symbol fixtures run in the digest-pinned acceptance lane",
    ),
]


def _run_export(
    tmp_path: Path,
    case: str,
    repeat: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    output = tmp_path / "native-output"
    output.mkdir(exist_ok=True)
    netlist_path = output / f"{case}-{repeat}.netlist.xml"
    command = execute_kicad_cli(
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
            str(FIXTURES / f"{case}.kicad_sch"),
        ),
        tmp_path,
        home_directory=f"schematic-symbol-integrity-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    payload = ET.parse(netlist_path).getroot()
    references = tuple(sorted(item.attrib["ref"] for item in payload.findall("./components/comp")))

    source_root = tmp_path / f"{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=VERSION),
    )
    candidates = missing_embedded_library_symbol_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    return references, tuple(item.rule_id for item in candidates)


def test_native_netlist_omits_the_placed_symbol_and_source_lint_finds_it(
    tmp_path: Path,
) -> None:
    control_runs = tuple(_run_export(tmp_path, "control", repeat) for repeat in ("first", "repeat"))
    fault_runs = tuple(_run_export(tmp_path, "fault", repeat) for repeat in ("first", "repeat"))

    assert control_runs == ((("J1", "U1"), ()),) * 2
    assert fault_runs == ((("U1",), (RULE_ID,)),) * 2
