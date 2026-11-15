"""Exact-version native exports for connector peer function metadata review."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_identity import native_pin_metadata_is_missing
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.validate import read_netlist
from tests.connector_footprint_peer_support import lint_report
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "connector.footprint_peer_pin_function_metadata_incomplete"
_FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures/design_lint/connector-peer-pin-function-metadata-native"
)
_FIXTURES = {
    "fault": (
        _FIXTURE_ROOT / "generic-function-peer-fault.kicad_sch",
        "56118298a9cd7a567bfb4df115cf0b6f5fe7c64a3de2ad4984b28f3c10d2152e",
    ),
    "missing_fault": (
        _FIXTURE_ROOT / "missing-function-peer-fault.kicad_sch",
        "d244a846990c8d99fd0ae8219c9eab3900c37de58b91dd01f785f0adac755e22",
    ),
    "control": (
        _FIXTURE_ROOT / "metadata-matched-control.kicad_sch",
        "389c91306af19802373ee42ef5aebc8064e4a8e21b9c7758e916e658239a6469",
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
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_generic_or_missing_function_peer_metadata_review_and_control_repeat(
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
        home_directory=f"connector-function-metadata-{kicad_version}",
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
                home_directory=f"connector-function-metadata-{kicad_version}-{case}-{run}",
                fixture_directory=fixture_directory,
                output_directory=output_directory,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            exports.append(read_netlist(output))
            write_model(receipt_directory / f"{case}-{run}.command.json", command)
        assert exports[0] == exports[1]
        observations[case] = exports[0]

    fault, missing_fault, control = (
        observations["fault"],
        observations["missing_fault"],
        observations["control"],
    )
    assert fault.components["J1"].part_id == fault.components["J2"].part_id
    assert fault.components["J1"].part_id == "SYNTHETIC-PEER-001"
    assert fault.pin_functions["J1.2"] == "Pin_2"
    assert fault.pin_functions["J2.2"] == "UART_RX"
    assert fault.pin_electrical_types["J1.2"] == fault.pin_electrical_types["J2.2"] == "passive"
    assert fault.nets["SYNTHETIC_NET_2"] == ("J1.2", "J2.2")
    (finding,) = tuple(item for item in lint_report(fault).findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.evidence["peer_pin_functions"] == ("J1.2=Pin_2", "J2.2=UART_RX")
    assert missing_fault.components["J1"].part_id == missing_fault.components["J2"].part_id
    assert native_pin_metadata_is_missing(missing_fault.pin_functions.get("J1.2"))
    assert missing_fault.pin_functions["J2.2"] == "UART_RX"
    assert (
        missing_fault.pin_electrical_types["J1.2"]
        == missing_fault.pin_electrical_types["J2.2"]
        == "passive"
    )
    assert missing_fault.nets["SYNTHETIC_NET_2"] == ("J1.2", "J2.2")
    (missing_finding,) = tuple(
        item for item in lint_report(missing_fault).findings if item.rule_id == RULE_ID
    )
    assert missing_finding.mode == "review"
    assert missing_finding.evidence["missing_function_peers"] == ("J1",)
    assert missing_finding.evidence["peer_pin_functions"] == (
        "J1.2=<missing>",
        "J2.2=UART_RX",
    )
    assert control.pin_functions["J1.2"] == control.pin_functions["J2.2"] == "UART_RX"
    assert not tuple(item for item in lint_report(control).findings if item.rule_id == RULE_ID)
    assert_native_fixture_mounts(tmp_path, "receipts/control-repeat.command.json")
