"""Exact-version KiCad exports for named mapped peer-supply split review."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.validate import read_netlist
from tests.design_lint_fixtures.connector_mapped_peer_supply_split import (
    RULE_ID,
    mapped_peer_supply_coverage,
    mapped_peer_supply_report,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="exact-version native connector fixtures run in package acceptance",
    ),
]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/mapped-named-peer-supply-native"
EXPECTED_SOURCE_HASHES = {
    "fault.kicad_sch": "b066f0a88ea6b32205c96b99b23a1ce841a1772c8ea7294cfa9b4415e94d219a",
    "control.kicad_sch": "0feff0855ebb0338633c8c7ff71c19cd26724c1338005a1c48e95753cdf37d7f",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_named_peer_supply_split_fault_and_control(tmp_path: Path) -> None:
    for kicad_version, image in PINNED_NATIVE_KICAD_IMAGES.items():
        work = tmp_path / f"work-{kicad_version}"
        work.mkdir()
        output = tmp_path / f"output-{kicad_version}"
        output.mkdir()
        commands = output / "commands"
        commands.mkdir()

        version_command = execute_kicad_cli(
            image,
            ("kicad-cli", "version"),
            work,
            home_directory=f"mapped-named-peer-supply-version-{kicad_version}",
        )
        assert version_command.returncode == 0
        assert version_command.stdout.strip() == kicad_version

        for case in ("fault", "control"):
            fixture_name = f"{case}.kicad_sch"
            source = FIXTURES / fixture_name
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            assert source_hash == EXPECTED_SOURCE_HASHES[fixture_name]
            exports = []
            for run in ("first", "repeat"):
                netlist_path = output / f"{case}.{run}.netlist.xml"
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
                        str(netlist_path),
                        str(source),
                    ),
                    work,
                    home_directory=f"mapped-named-peer-supply-{kicad_version}-{case}-{run}",
                    fixture_directory=FIXTURES,
                    output_directory=output,
                )
                receipt = commands / f"{case}.{run}.command.json"
                write_model(receipt, command)
                assert command.returncode == 0, command.model_dump_json(indent=2)
                assert netlist_path.is_file()
                assert_native_fixture_mounts(tmp_path, receipt.relative_to(tmp_path).as_posix())
                exports.append((read_netlist(netlist_path), digest(netlist_path)))

            first, first_hash = exports[0]
            repeat, repeat_hash = exports[1]
            assert first == repeat
            assert len(first_hash) == len(repeat_hash) == 64
            assert first.pin_functions["J1.1"] == "CONTACT_A"
            assert first.pin_functions["J2.1"] == "CONTACT_B"
            report, coverage = mapped_peer_supply_report(
                first,
                coverage=mapped_peer_supply_coverage(first),
            )
            findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
            assert coverage.status == "COMPLETE"
            if case == "fault":
                (finding,) = findings
                assert finding.evidence["connector_references"] == ("J1", "J2")
                assert finding.evidence["split_native_nets"] == ("NODE_ALPHA", "NODE_BETA")
            else:
                assert not findings
