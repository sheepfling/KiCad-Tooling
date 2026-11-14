"""Exact-version KiCad exports for unanchored generic connector power-pin splits."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from kicad_tooling.validate import read_netlist
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "connector.footprint_peer_generic_power_pin_unanchored_split"
_FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint/connector-footprint-alias-native"
_FIXTURES = {
    "fault": (
        _FIXTURE_ROOT / "generic-power-unanchored-split-fault.kicad_sch",
        "99ee775ff9d7f0944b70c1a4ac0cfaaf94bd8115ede6f89afe1eba10c4528bae",
    ),
    "control": (
        _FIXTURE_ROOT / "generic-power-all-open-control.kicad_sch",
        "2edfe7572b8af9dcad081863b870dbb602a21abb13e0f07688cb683da35b9eb3",
    ),
}

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned acceptance lane",
    ),
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_generic_power_split_fault_and_common_control_repeat(
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
        home_directory=f"generic-power-split-{kicad_version}",
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
                home_directory=f"generic-power-split-{kicad_version}-{case}-{run}",
                fixture_directory=fixture_directory,
                output_directory=output_directory,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            exports.append(read_netlist(output))
            write_model(receipt_directory / f"{case}-{run}.command.json", command)
        assert exports[0] == exports[1]
        observations[case] = exports[0]

    fault = observations["fault"]
    assert fault.pin_functions["J1.2"] == fault.pin_functions["J2.2"] == "Pin_2"
    assert fault.pin_electrical_types["J1.2"] == fault.pin_electrical_types["J2.2"] == "power_in"
    assert fault.nets["POWER_A"] == ("J1.2",)
    assert fault.nets["POWER_B"] == ("J2.2",)
    fault_findings = tuple(
        item for item in connector_footprint_peer_pin_candidates(fault) if item.rule_id == RULE_ID
    )
    assert len(fault_findings) == 1
    assert fault_findings[0].evidence["assignments"] == ("J1.2=POWER_A", "J2.2=POWER_B")
    assert fault_findings[0].evidence["pin_electrical_type"] == ("power_in",)

    control_findings = tuple(
        item
        for item in connector_footprint_peer_pin_candidates(observations["control"])
        if item.rule_id == RULE_ID
    )
    assert control_findings == ()
    assert_native_fixture_mounts(tmp_path, "receipts/control-repeat.command.json")
