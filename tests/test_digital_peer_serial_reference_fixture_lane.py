"""Serial connector and labeled-reference fixture checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.design_lint_fixtures.digital_peer_serial import SERIAL_LABEL_EXPECTED_NETS

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

_FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures/design_lint/serial-peer-connector-reference-native"
)


@pytest.mark.parametrize(
    ("filename", "expected_sha256"),
    (
        pytest.param(
            "serial-label-control.kicad_sch",
            "a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561",
            id="label-control",
        ),
        pytest.param(
            "serial-label-fault.kicad_sch",
            "2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20",
            id="label-fault",
        ),
    ),
)
def test_serial_label_reference_fixture_matches_synthetic_digest(filename, expected_sha256) -> None:
    source = _FIXTURE_ROOT / filename
    text = source.read_text(encoding="utf-8")

    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
    assert "NOT FOR MANUFACTURE - tooling fixture" in text
    assert '"UART.0.TX"' in text
    assert '"UART.0.RX"' in text
    assert '"B2"' in text
    assert '"ADBUS1"' in text
    assert '(property "Reference" "U2"' in text
    assert '(property "Reference" "J1"' not in text


def test_serial_connector_reference_lane_reports_split_and_common_controls(
    digital_peer_fixture_results,
) -> None:
    results = digital_peer_fixture_results
    connector_control = results["spi-participant-fixture/serial-connector-control"]
    connector_fault = results["spi-participant-fixture/serial-connector-fault"]
    label_control = results["spi-participant-fixture/serial-label-control"]
    label_fault = results["spi-participant-fixture/serial-label-fault"]

    assert connector_control["peer_reference_findings"] == "none"
    assert connector_control["reference_assignments"] == "GND_A=J1.4,U1.4"
    assert connector_fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert connector_fault["reference_assignments"] == "GND_A=U1.4;GND_B=J1.4"
    assert label_control["lint_status"] == "REVIEW"
    assert label_control["peer_reference_findings"] == "none"
    assert label_control["reference_assignments"] == "GND_A=U1.4,U2.4"
    assert label_fault["lint_status"] == "REVIEW"
    assert label_fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert label_fault["reference_assignments"] == "GND_A=U1.4;GND_B=U2.4"
    assert label_fault["signal_assignments"] == ";".join(
        f"{net}={','.join(pins)}" for net, pins in sorted(SERIAL_LABEL_EXPECTED_NETS.items())
    )
    assert label_fault["pin_functions"] == (
        "U1.1=B2;U1.2=B1;U1.3=VDD;U1.4=GND;U2.1=ADBUS0;U2.2=ADBUS1;U2.3=VDD;U2.4=GND"
    )
    assert label_fault["pin_types"] == (
        "U1.1=output;U1.2=input;U1.3=power_in;U1.4=power_in;"
        "U2.1=input;U2.2=output;U2.3=passive;U2.4=passive"
    )

    for result in (connector_control, connector_fault, label_control, label_fault):
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
