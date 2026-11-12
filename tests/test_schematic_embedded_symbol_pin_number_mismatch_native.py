"""Exact KiCad evidence for a unique embedded symbol with changed pin numbers."""

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
    embedded_symbol_pin_number_mismatch_candidates,
)
from tests.native_kicad_support import execute_kicad_cli

RULE_ID = "schematic.embedded_symbol_pin_number_mismatch"
VERSION = "10.0.5"
IMAGE = (
    "ghcr.io/kicad/kicad:10.0.5@sha256:"
    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
)
FIXTURES = Path(__file__).parent / "fixtures/design_lint/embedded-symbol-pin-number-mismatch"
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
        reason="native symbol pin-number fixtures run in the digest-pinned acceptance lane",
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
        home_directory=f"symbol-pin-numbers-{case}-{repeat}",
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
    candidates = embedded_symbol_pin_number_mismatch_candidates(
        source_root,
        config,
        {SCHEMATIC: digest(source_path)},
    )
    return contract, tuple(item.rule_id for item in candidates)


def test_native_unique_definition_pin_number_mismatch_changes_exported_net_pin(
    tmp_path: Path,
) -> None:
    control_runs = tuple(_run_export(tmp_path, "control", run) for run in ("first", "repeat"))
    fault_runs = tuple(_run_export(tmp_path, "fault", run) for run in ("first", "repeat"))

    assert control_runs[0] == control_runs[1]
    assert fault_runs[0] == fault_runs[1]
    control_netlist, control_rules = control_runs[0]
    fault_netlist, fault_rules = fault_runs[0]
    assert set(control_netlist.components) == {"J1", "U1"}
    assert control_netlist.nets["USB_GND"] == ("J1.4",)
    assert fault_netlist.nets["USB_GND"] == ("J1.9",)
    assert control_rules == ()
    assert fault_rules == (RULE_ID,)


def test_native_matching_multi_unit_group_controls_exported_net_pin(tmp_path: Path) -> None:
    control_runs = tuple(
        _run_export(tmp_path, "multi-unit-control", run) for run in ("first", "repeat")
    )
    fault_runs = tuple(
        _run_export(tmp_path, "multi-unit-fault", run) for run in ("first", "repeat")
    )

    assert control_runs[0] == control_runs[1]
    assert fault_runs[0] == fault_runs[1]
    control_netlist, control_rules = control_runs[0]
    fault_netlist, fault_rules = fault_runs[0]
    assert set(control_netlist.components) == {"J1", "U1"}
    assert control_netlist.nets["USB_GND"] == ("J1.5",)
    assert fault_netlist.nets["USB_GND"] == ("J1.9",)
    assert control_rules == ()
    assert fault_rules == (RULE_ID,)


def test_native_shared_unit_zero_and_selected_group_are_compared(tmp_path: Path) -> None:
    control_runs = tuple(
        _run_export(tmp_path, "shared-unit-zero-control", run) for run in ("first", "repeat")
    )
    fault_runs = tuple(
        _run_export(tmp_path, "shared-unit-zero-fault", run) for run in ("first", "repeat")
    )

    assert control_runs[0] == control_runs[1]
    assert fault_runs[0] == fault_runs[1]
    control_netlist, control_rules = control_runs[0]
    fault_netlist, fault_rules = fault_runs[0]
    assert control_netlist.nets["USB_GND"] == ("J1.5",)
    assert control_netlist.nets["USB_SHARED"] == ("J1.8",)
    assert fault_netlist.nets["USB_GND"] == ("J1.9",)
    assert fault_netlist.nets["USB_SHARED"] == ("J1.8",)
    assert control_rules == ()
    assert fault_rules == (RULE_ID,)
