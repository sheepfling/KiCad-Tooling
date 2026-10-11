"""Digest-pinned native SPI peer fixture regressions."""

from __future__ import annotations

import pytest

from tests.digital_peer_native_acceptance import NATIVE_DIGITAL_PEER_PROJECTS

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_spi_roster_and_signal_voltage_cases_by_native_version(
    native_digital_peer_results, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    unrostered = results["spi-participant-fixture/unrostered"]
    rostered = results["spi-participant-fixture/rostered"]
    voltage_control = results["spi-participant-fixture/voltage-control"]
    voltage_fault = results["spi-participant-fixture/voltage-fault"]

    assert unrostered["kicad_version"] == version
    assert unrostered["status"] == "PASS"
    assert unrostered["lint_status"] == "REVIEW"
    assert set(str(unrostered["findings"]).split(";")) == {
        "U1: SPI roster coverage",
        "U2: SPI roster coverage",
    }
    assert unrostered["pin_functions"] == (
        "U1.1=SPI1_SCLK;U1.2=SPI1_COPI;U1.3=SPI1_CIPO;U1.4=SPI1_NSS;"
        "U2.1=SPI1_SCLK;U2.2=SPI1_COPI;U2.3=SPI1_CIPO;U2.4=SPI1_NSS"
    )
    assert rostered["status"] == "PASS"
    assert rostered["lint_status"] == "PASS"
    assert rostered["findings"] == "none"
    assert voltage_control["compatibility_status"] == "PASS"
    assert float(str(voltage_control["minimum_margin_v"])) == pytest.approx(0.3)
    assert voltage_control["driver"] == "U1.2/SPI_MOSI"
    assert voltage_control["receiver"] == "U2.2/SPI_MOSI"
    assert voltage_fault["compatibility_status"] == "FAIL"
    assert float(str(voltage_fault["minimum_margin_v"])) == pytest.approx(-1.4)
    assert voltage_fault["driver"] == "U1.2/SPI_MOSI"
    assert voltage_fault["receiver"] == "U2.2/SPI_MOSI"


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_spi_peer_voltage_fault_and_controls_by_native_version(
    native_digital_peer_results, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["spi-participant-fixture/peer-control"]
    fault = results["spi-participant-fixture/peer-fault"]
    translator = results["spi-participant-fixture/peer-translator-control"]

    assert control["kicad_version"] == version
    assert control["lint_status"] == "PASS"
    assert control["peer_voltage_findings"] == "none"
    assert control["rail_assignments"] == "+3V3=U1.2,U2.2"
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_voltage_findings"] == "bus.spi_peer_voltage_review"
    assert fault["rail_assignments"] == "+3V3=U2.2;+5V=U1.2"
    assert fault["pin_functions"] == "U1.1=SPI1_SCLK;U1.2=VDD;U2.1=SPI1_SCLK;U2.2=VDD"
    assert fault["pin_types"] == "U1.1=output;U1.2=power_in;U2.1=input;U2.2=power_in"
    assert translator["lint_status"] == "PASS"
    assert translator["peer_voltage_findings"] == "none"
    assert translator["signal_assignments"] == "SPI_A_SIDE=U1.1,U3.1;SPI_B_SIDE=U2.1,U3.2"
    assert translator["rail_assignments"] == "+3V3=U2.2,U3.4;+5V=U1.2,U3.3"


def test_spi_peer_normalized_netlists_match_across_native_versions(
    native_digital_peer_results,
) -> None:
    digests = {
        version: tuple(
            native_digital_peer_results[project][stage]["normalized_netlist_sha256"]
            for stage in (
                "spi-participant-fixture/peer-control",
                "spi-participant-fixture/peer-fault",
                "spi-participant-fixture/peer-translator-control",
            )
        )
        for project, version in NATIVE_DIGITAL_PEER_PROJECTS
    }
    assert digests["10.0.0"] == digests["10.0.5"]
