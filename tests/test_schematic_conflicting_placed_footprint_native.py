"""Exact KiCad 10.0.8 behavior for conflicting placed Footprint properties."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.schematic_conflicting_placed_footprint import (
    source_bound_conflicting_placed_footprint_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.conflicting_placed_footprint_properties"
VERSION = "10.0.8"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.8@sha256:"
    "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
)
FIXTURES = Path(__file__).parent / "fixtures/design_lint/conflicting-placed-footprint"
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
        reason="native schematic source-integrity fixtures run in the pinned acceptance lane",
    ),
]


def _run_export(tmp_path: Path, case: str, repeat: str) -> tuple[str, tuple[str, ...]]:
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
        home_directory=f"conflicting-placed-footprint-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    assert "<tool>Eeschema 10.0.8</tool>" in netlist_path.read_text(encoding="utf-8")
    contract = read_netlist(netlist_path)

    source_root = tmp_path / f"{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=VERSION),
    )
    candidates = source_bound_conflicting_placed_footprint_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    return contract.components["J1"].footprint, tuple(item.rule_id for item in candidates)


def test_native_export_uses_last_conflicting_footprint_and_controls_stay_quiet(
    tmp_path: Path,
) -> None:
    fault = tuple(_run_export(tmp_path, "fault", repeat) for repeat in ("first", "repeat"))
    control = tuple(_run_export(tmp_path, "control", repeat) for repeat in ("first", "repeat"))
    same_duplicate = tuple(
        _run_export(tmp_path, "control-duplicate-same-footprint", repeat)
        for repeat in ("first", "repeat")
    )
    library_duplicate = tuple(
        _run_export(tmp_path, "library-only-duplicate", repeat) for repeat in ("first", "repeat")
    )

    assert fault == (("Synthetic:Wrong", (RULE_ID,)),) * 2
    assert control == (("Synthetic:USB-A", ()),) * 2
    assert same_duplicate == (("Synthetic:USB-A", ()),) * 2
    assert library_duplicate == (("Synthetic:USB-A", ()),) * 2
