"""Exact-version native exports for connector peer pin-inventory review."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_inventory_consistency import (
    connector_footprint_peer_pin_inventory_disagreements,
)
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.validate import read_netlist
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "connector.footprint_peer_pin_inventory_disagreement"
_FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint/connector-peer-pin-function-native"
_FIXTURES = {
    "fault": (
        _FIXTURE_ROOT / "pin-inventory-disagreement-fault.kicad_sch",
        "b50a7d3c49ff20220e613373c15e0ebf68ad5eabe7bfc428d83647720743c25f",
    ),
    "control": (
        _FIXTURE_ROOT / "pin-function-matched-control.kicad_sch",
        "01d44e2b8f5a5a41fc830f8eea20161c6fc363075f62c8b0cc35bc6cbbf5f335",
    ),
}

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned acceptance lane",
    ),
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_connector_peer_pin_inventory_difference_and_control_repeat(
    tmp_path: Path,
    kicad_version: str,
) -> None:
    fixture_directory = tmp_path / "fixtures"
    output_directory = tmp_path / "outputs"
    receipt_directory = tmp_path / "receipts"
    for directory in (fixture_directory, output_directory, receipt_directory):
        directory.mkdir(parents=True, exist_ok=True)

    image = PINNED_NATIVE_KICAD_IMAGES[kicad_version]
    version = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        tmp_path,
        home_directory=f"connector-peer-inventory-{kicad_version}",
        fixture_directory=fixture_directory,
        output_directory=output_directory,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == kicad_version

    observations = {}
    for case, (fixture, source_sha256) in _FIXTURES.items():
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == source_sha256
        source = fixture_directory / fixture.name
        shutil.copyfile(fixture, source)
        exports = []
        for run in ("first", "repeat"):
            output = output_directory / f"{case}-{run}.netlist.xml"
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
                home_directory=f"connector-peer-inventory-{kicad_version}-{case}-{run}",
                fixture_directory=fixture_directory,
                output_directory=output_directory,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            exports.append(read_netlist(output))
            write_model(receipt_directory / f"{case}-{run}.command.json", command)
        assert exports[0] == exports[1]
        observations[case] = exports[0]

    fault, control = observations["fault"], observations["control"]
    assert fault.components["J1"].part_id == fault.components["J2"].part_id
    assert fault.component_pin_numbers["J1"] == ("1", "2")
    assert fault.component_pin_numbers["J2"] == ("1", "2", "3")
    assert fault.pin_functions["J2.3"] == "VBUS"
    assert fault.pin_electrical_types["J2.3"] == "power_in"
    assert fault.nets["SYNTHETIC_NET_3"] == ("J2.3",)
    (finding,) = connector_footprint_peer_pin_inventory_disagreements(fault)
    assert finding.rule_id == RULE_ID
    assert finding.evidence["peer_pin_inventories"] == ("J1=1,2", "J2=1,2,3")
    assert finding.evidence["extra_pin"] == ("J2.3",)
    assert finding.evidence["extra_pin_assignments"] == ("J2.3=SYNTHETIC_NET_3",)
    assert (
        control.component_pin_numbers["J1"]
        == control.component_pin_numbers["J2"]
        == (
            "1",
            "2",
        )
    )
    assert connector_footprint_peer_pin_inventory_disagreements(control) == ()
    assert_native_fixture_mounts(tmp_path, "receipts/control-repeat.command.json")
