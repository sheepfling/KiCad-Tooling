"""Exact KiCad evidence for duplicated schematic object UUID behavior."""

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
from kicad_tooling.hwrepo.schematic_source_integrity import (
    duplicate_schematic_object_uuid_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.duplicate_object_uuid"
VERSION = "10.0.5"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.5@sha256:"
    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
)
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-duplicate-object-uuid"
HIERARCHY_FIXTURES = (
    Path(__file__).parent / "fixtures/design_lint/schematic-duplicate-object-uuid-across-files"
)
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
HIERARCHICAL_SOURCES = (
    SCHEMATIC,
    "projects/synthetic/channel-a.kicad_sch",
    "projects/synthetic/channel-b.kicad_sch",
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_SYMBOL_INTEGRITY_FIXTURES") != "1",
        reason="native schematic UUID fixtures run in the digest-pinned acceptance lane",
    ),
]


def _run_export(tmp_path: Path, case: str, repeat: str):
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
        home_directory=f"duplicate-object-uuid-{case}-{repeat}",
        fixture_directory=FIXTURES,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    contract = read_netlist(netlist_path)

    source_root = tmp_path / f"{case}-{repeat}-source"
    source_path = source_root / SCHEMATIC
    source_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_sch", source_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=VERSION),
    )
    candidates = duplicate_schematic_object_uuid_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    return contract, tuple(item.rule_id for item in candidates)


def _run_hierarchical_export(tmp_path: Path, case: str, repeat: str):
    run_root = tmp_path / f"{case}-{repeat}"
    fixture_directory = run_root / "native-project"
    fixture_directory.mkdir(parents=True)
    shutil.copyfile(
        HIERARCHY_FIXTURES / "root.kicad_sch",
        fixture_directory / "controller.kicad_sch",
    )
    shutil.copyfile(
        HIERARCHY_FIXTURES / "channel-a.kicad_sch",
        fixture_directory / "channel-a.kicad_sch",
    )
    channel_b = "channel-b-control.kicad_sch" if case == "control" else "channel-b-fault.kicad_sch"
    shutil.copyfile(HIERARCHY_FIXTURES / channel_b, fixture_directory / "channel-b.kicad_sch")

    output = run_root / "native-output"
    output.mkdir()
    netlist_path = output / "hierarchical.netlist.xml"
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
            str(fixture_directory / "controller.kicad_sch"),
        ),
        tmp_path,
        home_directory=f"duplicate-object-uuid-hierarchy-{case}-{repeat}",
        fixture_directory=fixture_directory,
        output_directory=output,
    )
    assert command.error is None, command.model_dump_json(indent=2)
    assert command.returncode == 0, command.model_dump_json(indent=2)
    contract = read_netlist(netlist_path)

    source_root = run_root / "source"
    source_names = ("controller.kicad_sch", "channel-a.kicad_sch", "channel-b.kicad_sch")
    for relative, source_name in zip(HIERARCHICAL_SOURCES, source_names, strict=True):
        source_path = source_root / relative
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_directory / source_name, source_path)
    source_hashes = {relative: digest(source_root / relative) for relative in HIERARCHICAL_SOURCES}
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version=VERSION),
    )
    candidates = duplicate_schematic_object_uuid_candidates(source_root, config, source_hashes)
    return contract, candidates


def test_native_duplicate_uuid_is_accepted_without_netlist_change(tmp_path: Path) -> None:
    control_runs = tuple(_run_export(tmp_path, "control", run) for run in ("first", "repeat"))
    fault_runs = tuple(_run_export(tmp_path, "fault", run) for run in ("first", "repeat"))

    assert control_runs[0] == control_runs[1]
    assert fault_runs[0] == fault_runs[1]
    control_netlist, control_rules = control_runs[0]
    fault_netlist, fault_rules = fault_runs[0]
    assert set(control_netlist.components) == {"J1", "U1"}
    assert control_netlist.nets == fault_netlist.nets
    assert control_netlist.nets["USB_GND"] == ("J1.4",)
    assert control_rules == ()
    assert fault_rules == (RULE_ID,)


def test_native_cross_file_uuid_collision_is_review_only_and_repeatable(
    tmp_path: Path,
) -> None:
    control_runs = tuple(
        _run_hierarchical_export(tmp_path, "control", run) for run in ("first", "repeat")
    )
    fault_runs = tuple(
        _run_hierarchical_export(tmp_path, "fault", run) for run in ("first", "repeat")
    )

    assert control_runs[0] == control_runs[1]
    assert fault_runs[0] == fault_runs[1]
    control_netlist, control_candidates = control_runs[0]
    fault_netlist, fault_candidates = fault_runs[0]
    assert set(control_netlist.components) == {"R1", "R2"}
    assert fault_netlist == control_netlist
    assert control_candidates == ()
    assert len(fault_candidates) == 1
    assert fault_candidates[0].rule_id == RULE_ID
    assert fault_candidates[0].evidence["object_uuid"] == ("b0000000-0000-4000-8000-000000000005",)
