"""SPI peer-voltage hosted-lane fixture and result checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/design_lint/spi-peer-voltage-native"


@pytest.mark.parametrize(
    ("filename", "expected_sha256"),
    (
        pytest.param(
            "peer-control.kicad_sch",
            "427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd",
            id="peer-control",
        ),
        pytest.param(
            "peer-fault.kicad_sch",
            "98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4",
            id="peer-fault",
        ),
        pytest.param(
            "peer-translator-control.kicad_sch",
            "58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1",
            id="translator-control",
        ),
    ),
)
def test_spi_peer_voltage_fixture_matches_synthetic_digest(filename, expected_sha256) -> None:
    source = _FIXTURE_ROOT / filename
    text = source.read_text(encoding="utf-8")

    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
    assert "NOT FOR MANUFACTURE - tooling fixture" in text


def test_spi_translator_fixture_declares_both_voltage_sides() -> None:
    text = (_FIXTURE_ROOT / "peer-translator-control.kicad_sch").read_text(encoding="utf-8")

    for pin_name in ('"A_SCLK"', '"B_SCLK"', '"VCCA"', '"VCCB"'):
        assert pin_name in text


def test_spi_peer_voltage_lane_reports_fault_control_and_translator(
    digital_peer_fixture_results,
) -> None:
    results = digital_peer_fixture_results
    control = results["spi-participant-fixture/peer-control"]
    fault = results["spi-participant-fixture/peer-fault"]
    translator = results["spi-participant-fixture/peer-translator-control"]

    assert control["lint_status"] == "PASS"
    assert control["peer_voltage_findings"] == "none"
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_voltage_findings"] == "bus.spi_peer_voltage_review"
    assert fault["pin_types"] == "U1.1=output;U1.2=power_in;U2.1=input;U2.2=power_in"
    assert fault["rail_assignments"] == "+3V3=U2.2;+5V=U1.2"
    assert translator["lint_status"] == "PASS"
    assert translator["peer_voltage_findings"] == "none"
    assert translator["pin_functions"] == (
        "U1.1=SPI1_SCLK;U1.2=VDD;U1.3=GND;U2.1=SPI1_SCLK;U2.2=VDD;"
        "U2.3=GND;U3.1=A_SCLK;U3.2=B_SCLK;U3.3=VCCA;U3.4=VCCB;U3.5=GND"
    )
    assert translator["rail_assignments"] == "+3V3=U2.2,U3.4;+5V=U1.2,U3.3"
    assert translator["signal_assignments"] == "SPI_A_SIDE=U1.1,U3.1;SPI_B_SIDE=U2.1,U3.2"

    for result in (control, fault, translator):
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
