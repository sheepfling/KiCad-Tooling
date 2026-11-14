"""Digest-pinned native netlist evidence for power-pin width-map coverage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.pcb_power_pin_track_width_coverage import (
    RULE_ID,
    power_pin_net_track_width_map_candidates,
)
from kicad_tooling.hwrepo.project_models import ProjectKind
from tests.design_lint_fixtures.pcb_power_pin_track_width import power_track_width_map
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_POWER_PIN_WIDTH_MAP_FIXTURES") != "1",
        reason="native power-pin width-map fixtures use digest-pinned KiCad 10 images",
    ),
]

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures/design_lint/switching-regulator-loop-map-native/unmapped.kicad_sch"
)
EXPECTED_SOURCE_SHA256 = "48f279e9a59754ab1c414138f8dafab15e8c933a5ac953a3faf845c7fb51d7cf"


def test_native_power_pin_nets_prompt_without_map_and_clear_when_mapped(
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
                home_directory=f"power-width-map-{version}-{output.stem}",
                fixture_directory=fixture_dir,
                output_directory=output_dir,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            assert output.is_file()

        observed = read_netlist(first)
        assert observed == read_netlist(repeat)
        assert observed.pin_electrical_types["U1.1"] == "power_in"
        assert observed.pin_electrical_types["U1.4"] == "power_in"
        fault = power_pin_net_track_width_map_candidates(observed, ProjectKind.PCB, None, "b" * 64)
        partial_control = power_pin_net_track_width_map_candidates(
            observed, ProjectKind.PCB, power_track_width_map("INPUT"), "b" * 64
        )
        mapped_control = power_pin_net_track_width_map_candidates(
            observed, ProjectKind.PCB, power_track_width_map("INPUT", "RETURN"), "b" * 64
        )

        assert {item.rule_id for item in fault} == {RULE_ID}
        assert {item.evidence["net"][0] for item in fault} == {"INPUT", "RETURN"}
        assert {item.evidence["net"][0] for item in partial_control} == {"RETURN"}
        assert mapped_control == ()
