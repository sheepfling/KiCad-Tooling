"""Serial peer-voltage hosted-lane fixture and result checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/design_lint/serial-peer-voltage-native"


@pytest.mark.parametrize(
    ("filename", "expected_sha256"),
    (
        pytest.param(
            "serial-control.kicad_sch",
            "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
            id="serial-control",
        ),
        pytest.param(
            "serial-fault.kicad_sch",
            "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
            id="serial-fault",
        ),
        pytest.param(
            "serial-reference-fault.kicad_sch",
            "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
            id="serial-reference-fault",
        ),
    ),
)
def test_serial_peer_voltage_fixture_matches_synthetic_digest(filename, expected_sha256) -> None:
    source = _FIXTURE_ROOT / filename
    text = source.read_text(encoding="utf-8")

    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
    assert "NOT FOR MANUFACTURE - tooling fixture" in text
    assert '"UART1_TX"' in text
    assert '"UART1_RX"' in text


def test_serial_peer_voltage_lane_separates_supply_and_reference_findings(
    digital_peer_fixture_results,
) -> None:
    results = digital_peer_fixture_results
    control = results["spi-participant-fixture/serial-control"]
    fault = results["spi-participant-fixture/serial-fault"]
    reference_fault = results["spi-participant-fixture/serial-reference-fault"]

    assert control["lint_status"] == "PASS"
    assert control["peer_voltage_findings"] == "none"
    assert control["peer_reference_findings"] == "none"
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_voltage_findings"] == "bus.serial_peer_voltage_review"
    assert fault["pin_functions"] == (
        "U1.1=UART1_TX;U1.2=VDD;U1.3=GND;U2.1=UART1_RX;U2.2=VDD;U2.3=GND"
    )
    assert fault["rail_assignments"] == "+3V3=U2.2;+5V=U1.2"
    assert reference_fault["lint_status"] == "REVIEW"
    assert reference_fault["peer_voltage_findings"] == "none"
    assert reference_fault["peer_reference_findings"] == "bus.serial_peer_reference_review"
    assert reference_fault["reference_assignments"] == "GND_A=U1.3;GND_B=U2.3"

    for result in (control, fault, reference_fault):
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
