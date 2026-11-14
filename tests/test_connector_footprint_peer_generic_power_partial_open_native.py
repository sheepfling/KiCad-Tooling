"""Digest-pinned Docker exports for partial-open generic power peers."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_coverage import source_matched_connector_peer_assignment_groups
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.validate import read_netlist
from tests.design_lint_fixtures.connector_peer_pin_all_open import generic_open_peer_coverage
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

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

RULE_ID = "connector.footprint_peer_generic_power_pin_open_outlier"
FIXTURE_ROOT = Path(__file__).parent / "fixtures/design_lint/connector-footprint-alias-native"
FIXTURES = {
    "fault": (
        FIXTURE_ROOT / "generic-power-partial-open-fault.kicad_sch",
        "f0355d80d5ac66bf3030829f70e10ad4d3261eaf60d80c1ad83ee299cfc68c68",
    ),
    "control": (
        FIXTURE_ROOT / "generic-power-all-open-control.kicad_sch",
        "2edfe7572b8af9dcad081863b870dbb602a21abb13e0f07688cb683da35b9eb3",
    ),
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_generic_power_partial_open_fault_and_control_repeat(
    tmp_path: Path,
    kicad_version: str,
) -> None:
    work = tmp_path / "native-work"
    fixture_dir = work / "fixtures"
    output_dir = work / "outputs"
    receipt_dir = tmp_path / "receipts"
    for directory in (fixture_dir, output_dir, receipt_dir):
        directory.mkdir(parents=True, exist_ok=True)
    image = PINNED_NATIVE_KICAD_IMAGES[kicad_version]
    version = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"generic-power-partial-open-{kicad_version}",
        fixture_directory=fixture_dir,
        output_directory=output_dir,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == kicad_version

    observed_by_case = {}
    for case, (fixture, source_hash) in FIXTURES.items():
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == source_hash
        source = fixture_dir / f"{case}.kicad_sch"
        shutil.copyfile(fixture, source)
        results = []
        for run in ("first", "repeat"):
            output = output_dir / f"{case}.{run}.netlist.xml"
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
                work,
                home_directory=f"generic-power-partial-open-{kicad_version}-{case}-{run}",
                fixture_directory=fixture_dir,
                output_directory=output_dir,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            results.append((read_netlist(output), digest(output)))
            write_model(receipt_dir / f"{case}-{run}.command.json", command)
        assert results[0][0] == results[1][0]
        observed_by_case[case] = results[0][0]

    fault = observed_by_case["fault"]
    control = observed_by_case["control"]
    assert fault.pin_electrical_types["J1.2"] == fault.pin_electrical_types["J2.2"] == "power_in"
    assert fault.nets == {"SYNTHETIC_NET_2": ("J1.2",)}
    assert control.nets["SYNTHETIC_NET_1"] == ("J1.1", "J2.1")
    assert control.nets["SYNTHETIC_NET_2"] == ("J1.2", "J2.2")

    coverage = generic_open_peer_coverage(fault, groups=("serial-peers", "serial-peers"))
    groups = source_matched_connector_peer_assignment_groups(fault, coverage)
    findings = tuple(
        item
        for item in connector_footprint_peer_pin_candidates(
            fault,
            peer_assignment_groups=groups,
            connector_coverage=coverage,
        )
        if item.rule_id == RULE_ID
    )
    assert len(findings) == 1
    assert findings[0].evidence["pin_electrical_type"] == ("power_in",)
    assert findings[0].evidence["common_anchor_pin_numbers"] == ()
    assert findings[0].evidence["peer_assignment_group"] == ("serial-peers",)
    assert not tuple(
        item for item in connector_footprint_peer_pin_candidates(control) if item.rule_id == RULE_ID
    )
    assert_native_fixture_mounts(tmp_path, "receipts/fault-repeat.command.json")
    assert_native_fixture_mounts(tmp_path, "receipts/control-repeat.command.json")
