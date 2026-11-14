"""Digest-pinned native netlist evidence for switching-regulator map coverage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.pcb_switching_loop_map_coverage import (
    switching_regulator_loop_map_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectKind
from tests.design_lint_fixtures.pcb_switching_regulator_loop_map import loop_map
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SWITCHING_REGULATOR_LOOP_MAP_FIXTURES") != "1",
        reason="native switching-regulator fixtures use digest-pinned KiCad 10 images",
    ),
]

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures/design_lint/switching-regulator-loop-map-native/unmapped.kicad_sch"
)
EXPECTED_SOURCE_SHA256 = "48f279e9a59754ab1c414138f8dafab15e8c933a5ac953a3faf845c7fb51d7cf"
RULE_ID = "pcb.switching_regulator_loop_map_coverage"


@pytest.mark.design_lint_rule(rule_id="pcb.switching_regulator_loop_map_coverage")
def test_native_switching_regulator_pin_inventory_and_map_coverage(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "outputs"
    fixture_dir.mkdir()
    output_dir.mkdir()
    source = fixture_dir / FIXTURE.name
    source.write_bytes(FIXTURE.read_bytes())

    for version, image in PINNED_NATIVE_KICAD_IMAGES.items():
        first = output_dir / f"{version}.first.netlist.xml"
        repeat = output_dir / f"{version}.repeat.netlist.xml"
        for output in (first, repeat):
            command = execute_kicad_cli(
                image,
                (
                    "kicad-cli",
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--output",
                    str(output),
                    str(source),
                ),
                tmp_path,
                home_directory=f"switching-loop-map-{version}-{output.stem}",
                fixture_directory=fixture_dir,
                output_directory=output_dir,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            assert output.is_file()

        observed = read_netlist(first)
        repeated = read_netlist(repeat)
        assert observed == repeated
        assert observed.component_symbols["U1"] == "Regulator_Switching:SyntheticBuck"
        assert observed.component_pin_numbers["U1"] == ("1", "2", "3", "4")
        assert observed.pin_functions["U1.2"] == "SW"
        assert observed.pin_functions["U1.3"] == "LX1"
        assert observed.pin_electrical_types["U1.2"] == "passive"
        assert observed.pin_electrical_types["U1.3"] == "passive"
        assert {item.rule_id for item in switching_regulator_loop_map_candidates(
            observed, ProjectKind.PCB, None, "b" * 64
        )} == {RULE_ID}
        assert switching_regulator_loop_map_candidates(
            observed,
            ProjectKind.PCB,
            loop_map(("U1.2", "U1.3")),
            "b" * 64,
        ) == ()
