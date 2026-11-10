"""Exact-version native exports for named mapped peer-signal split review."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.validate import read_netlist
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_report,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="exact-version native connector fixtures run in package acceptance",
    ),
]

RULE_ID = "connector.mapped_named_peer_signal_split_nets"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/mapped-named-peer-signal-native"
EXPECTED_SOURCE_HASHES = {
    "fault.kicad_sch": "4176ca5edf852912528c85f27d3eab741d19046dbf641b0121fddc9f7716168c",
    "control.kicad_sch": "62c73dd6569fbdbfd716632da1b98ffb2809b30e1a6fe25ba882463480c38d04",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_mapped_named_peer_signal_split_fault_and_control(tmp_path: Path) -> None:
    for kicad_version, image in PINNED_NATIVE_KICAD_IMAGES.items():
        work = tmp_path / f"work-{kicad_version}"
        work.mkdir()
        output = tmp_path / f"output-{kicad_version}"
        output.mkdir()
        version_command = execute_kicad_cli(
            image,
            ("kicad-cli", "version"),
            work,
            home_directory=f"mapped-named-peer-signal-version-{kicad_version}",
        )
        assert version_command.returncode == 0
        assert version_command.stdout.strip() == kicad_version
        for case in ("fault", "control"):
            fixture_name = f"{case}.kicad_sch"
            source = FIXTURES / fixture_name
            assert (
                hashlib.sha256(source.read_bytes()).hexdigest()
                == EXPECTED_SOURCE_HASHES[fixture_name]
            )
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
                    home_directory=f"mapped-named-peer-signal-{kicad_version}-{case}-{run}",
                    fixture_directory=FIXTURES,
                    output_directory=output,
                )
                receipt = output / f"{case}.{run}.command.json"
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
            assert first.nets.get("NODE_ALPHA") == (("J1.1",) if case == "fault" else None)
            assert first.nets.get("NODE_BETA") == (("J2.1",) if case == "fault" else None)

            coverage = peer_signal_coverage(
                first,
                references=("J1", "J2"),
                pins=("J1.1", "J2.1"),
            )
            report = peer_signal_report(first, coverage=coverage)
            findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
            assert coverage.status == "COMPLETE"
            if case == "fault":
                (finding,) = findings
                assert finding.evidence["connector_references"] == ("J1", "J2")
                assert finding.evidence["component_pin"] == ("J1.1", "J2.1")
                assert finding.evidence["split_native_nets"] == ("NODE_ALPHA", "NODE_BETA")
            else:
                assert not findings
                assert first.nets["COMMON_NODE"] == ("J1.1", "J2.1")
