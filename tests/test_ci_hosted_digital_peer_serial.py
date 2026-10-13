"""Digest-pinned native serial peer and reference-boundary regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.digital_peer_serial import SERIAL_LABEL_EXPECTED_NETS
from tests.digital_peer_native_acceptance import NATIVE_DIGITAL_PEER_PROJECTS

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

NativeDigitalPeerResults = dict[str, dict[str, dict[str, object]]]
_SERIAL_CONNECTOR_PIN_ROLE_METADATA = (
    "J1.1=UART1_RX/input;J1.2=UART1_TX/output;J1.3=VDD/passive;J1.4=GND/passive;"
    "U1.1=UART1_TX/output;U1.2=UART1_RX/input;U1.3=VDD/power_in;U1.4=GND/power_in"
)


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_serial_peer_voltage_fault_and_controls_by_native_version(
    native_digital_peer_results: NativeDigitalPeerResults, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["spi-participant-fixture/serial-control"]
    voltage_fault = results["spi-participant-fixture/serial-fault"]
    reference_fault = results["spi-participant-fixture/serial-reference-fault"]

    assert control["kicad_version"] == version
    assert control["lint_status"] == "PASS"
    assert control["peer_voltage_findings"] == "none"
    assert control["peer_reference_findings"] == "none"
    assert control["reference_assignments"] == "GND=U1.3,U2.3"
    assert control["rail_assignments"] == "+3V3=U1.2,U2.2"
    assert voltage_fault["lint_status"] == "REVIEW"
    assert voltage_fault["peer_voltage_findings"] == "bus.serial_peer_voltage_review"
    assert voltage_fault["peer_reference_findings"] == "none"
    assert voltage_fault["reference_assignments"] == "GND=U1.3,U2.3"
    assert voltage_fault["rail_assignments"] == "+3V3=U2.2;+5V=U1.2"
    assert voltage_fault["pin_functions"] == (
        "U1.1=UART1_TX;U1.2=VDD;U1.3=GND;U2.1=UART1_RX;U2.2=VDD;U2.3=GND"
    )
    assert voltage_fault["pin_types"] == (
        "U1.1=output;U1.2=power_in;U1.3=power_in;U2.1=input;U2.2=power_in;U2.3=power_in"
    )
    assert reference_fault["lint_status"] == "REVIEW"
    assert reference_fault["peer_voltage_findings"] == "none"
    assert reference_fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert reference_fault["reference_assignments"] == "GND_A=U1.3;GND_B=U2.3"
    assert reference_fault["rail_assignments"] == "+3V3=U1.2,U2.2"


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_serial_connector_and_optical_isolation_boundaries_by_native_version(
    native_digital_peer_results: NativeDigitalPeerResults, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["spi-participant-fixture/serial-connector-control"]
    fault = results["spi-participant-fixture/serial-connector-fault"]
    isolation = results["spi-participant-fixture/serial-optical-isolation-control"]

    assert control["kicad_version"] == version
    assert control["lint_status"] == "REVIEW"
    assert control["peer_reference_findings"] == "none"
    assert control["reference_assignments"] == "GND_A=J1.4,U1.4"
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert fault["reference_assignments"] == "GND_A=U1.4;GND_B=J1.4"
    assert fault["signal_assignments"] == "UART_RX=J1.2,U1.2;UART_TX=J1.1,U1.1"
    assert fault["pin_functions"] == (
        "J1.1=UART1_RX;J1.2=UART1_TX;J1.3=VDD;J1.4=GND;"
        "U1.1=UART1_TX;U1.2=UART1_RX;U1.3=VDD;U1.4=GND"
    )
    assert fault["pin_types"] == (
        "J1.1=input;J1.2=output;J1.3=passive;J1.4=passive;"
        "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in"
    )
    assert isolation["peer_reference_findings"] == "none"
    assert isolation["reference_assignments"] == ("GND_DEVICE=U2.4,U3.8;GND_HOST=U1.4,U3.6")


@pytest.mark.evidence_lint
@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_native_connectivity_snapshot_captures_pin_roles_by_version(
    native_digital_peer_results: NativeDigitalPeerResults, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["spi-participant-fixture/serial-connector-control"]
    fault = results["spi-participant-fixture/serial-connector-fault"]

    for result in (control, fault):
        assert result["kicad_version"] == version
        assert result["connectivity_snapshot_schema_version"] == "2"
        assert result["pin_metadata_coverage"] == "COMPLETE"
        assert result["pin_role_metadata"] == _SERIAL_CONNECTOR_PIN_ROLE_METADATA


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_serial_label_alias_fault_and_control_by_native_version(
    native_digital_peer_results: NativeDigitalPeerResults, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["spi-participant-fixture/serial-label-control"]
    fault = results["spi-participant-fixture/serial-label-fault"]

    assert control["kicad_version"] == version
    assert control["lint_status"] == "REVIEW"
    assert control["peer_reference_findings"] == "none"
    assert control["reference_assignments"] == "GND_A=U1.4,U2.4"
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert fault["reference_assignments"] == "GND_A=U1.4;GND_B=U2.4"
    assert fault["signal_assignments"] == ";".join(
        f"{net}={','.join(pins)}" for net, pins in sorted(SERIAL_LABEL_EXPECTED_NETS.items())
    )
    assert fault["pin_functions"] == (
        "U1.1=B2;U1.2=B1;U1.3=VDD;U1.4=GND;U2.1=ADBUS0;U2.2=ADBUS1;U2.3=VDD;U2.4=GND"
    )
    assert fault["pin_types"] == (
        "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in;"
        "U2.1=input;U2.2=output;U2.3=passive;U2.4=passive"
    )


def test_serial_peer_normalized_netlists_match_across_native_versions(
    native_digital_peer_results: NativeDigitalPeerResults,
) -> None:
    stage_groups = (
        ("serial-control", "serial-fault", "serial-reference-fault"),
        (
            "serial-connector-control",
            "serial-connector-fault",
            "serial-optical-isolation-control",
        ),
        ("serial-label-control", "serial-label-fault"),
    )
    for prefix in stage_groups:
        stages = tuple(f"spi-participant-fixture/{item}" for item in prefix)
        hashes_by_version = {
            version: tuple(
                native_digital_peer_results[project][stage]["normalized_netlist_sha256"]
                for stage in stages
            )
            for project, version in NATIVE_DIGITAL_PEER_PROJECTS
        }
        assert hashes_by_version["10.0.0"] == hashes_by_version["10.0.5"]

    serial_hashes = tuple(
        native_digital_peer_results["controller"][f"spi-participant-fixture/{stage}"][
            "normalized_netlist_sha256"
        ]
        for stage in ("serial-control", "serial-fault", "serial-reference-fault")
    )
    assert serial_hashes == (
        "ab26230622e20694fa31df7921381d1c0b629a2f4b5b99a24aa05e7ffa99aac8",
        "c5781c55ed8d12e5fa71b6d4302e9de5893d29014ad392c9e8a6b942368ea11c",
        "c92f4dffc776643127fb64b419f0d117acc97c6ec800549b51e990c407b5da60",
    )
