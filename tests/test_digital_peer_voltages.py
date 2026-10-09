"""Exact project-authored voltage limits for direct digital peer links."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.digital_peer_voltages import digital_peer_voltage_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
    NetlistContract,
)


def requirement(
    *,
    output_high_minimum_v: float = 2.2,
    output_high_maximum_v: float = 3.3,
    output_low_maximum_v: float = 0.4,
    include_limits: bool = True,
) -> DigitalPeerVoltageAnalysis:
    limits = {
        "output_limits": DigitalLogicOutputLimits(
            low_minimum_v=0.0,
            low_maximum_v=output_low_maximum_v,
            high_minimum_v=output_high_minimum_v,
            high_maximum_v=output_high_maximum_v,
            source="Synthetic controller datasheet Rev A, Table 8",
            conditions="VDD=3.3 V, specified output load, full operating range",
        ),
        "input_limits": DigitalLogicInputLimits(
            absolute_minimum_v=-0.3,
            low_maximum_v=0.8,
            high_minimum_v=2.0,
            absolute_maximum_v=3.6,
            source="Synthetic peripheral datasheet Rev B, Table 4",
            conditions="VDD=3.3 V, full operating range",
        ),
    }
    if not include_limits:
        limits = {"output_limits": None, "input_limits": None}
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic SPI data output mapped to a local peripheral input",
        links=(
            DigitalPeerVoltageLink(
                id="spi-mosi",
                basis="Reviewed controller-to-peripheral MOSI connection",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:Controller",
                    footprint="Package_QFP:LQFP-48",
                    pin="U1.12",
                    net="SPI_MOSI",
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:Peripheral",
                    footprint="Package_SO:SOIC-8",
                    pin="U2.3",
                    net="SPI_MOSI",
                ),
                **limits,
            ),
        ),
    )


def observed(*, fault: str | None = None) -> NetlistContract:
    u1_net = "SPI_MOSI"
    u2_net = "SPI_MOSI"
    dnp: tuple[str, ...] = ()
    if fault == "wrong-net":
        u2_net = "OTHER"
    elif fault == "dnp":
        dnp = ("U2",)
    elif fault == "wrong-symbol":
        pass
    nets = (
        {u1_net: ("U1.12", "U2.3")} if u1_net == u2_net else {u1_net: ("U1.12",), u2_net: ("U2.3",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic controller", footprint="Package_QFP:LQFP-48"),
            "U2": ComponentContract(value="Synthetic peripheral", footprint="Package_SO:SOIC-8"),
        },
        nets=nets,
        component_symbols={
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:OtherPeripheral"
            if fault == "wrong-symbol"
            else "Synthetic:Peripheral",
        },
        component_pin_numbers={"U1": ("12",), "U2": ("3",)},
        dnp_components=dnp,
    )


def checks(spec: DigitalPeerVoltageAnalysis | None = None, *, fault: str | None = None):
    result = digital_peer_voltage_checks(spec or requirement(), observed(fault=fault))
    return {item.id: item for item in result}


def test_authored_spi_limits_pass_at_exactly_supported_ranges() -> None:
    result = checks()
    assert result["digital-peer-voltage/spi-mosi/driver/identity"].status == "PASS"
    assert result["digital-peer-voltage/spi-mosi/receiver/pin"].status == "PASS"
    compatibility = result["digital-peer-voltage/spi-mosi/compatibility"]
    assert compatibility.status == "PASS"
    assert compatibility.observed == pytest.approx(0.2)
    assert "Synthetic controller datasheet" in compatibility.detail
    assert "VDD=3.3 V" in compatibility.detail


@pytest.mark.parametrize(
    "spec",
    (
        pytest.param(requirement(output_low_maximum_v=0.9), id="output-low-maximum"),
        pytest.param(requirement(output_high_minimum_v=1.8), id="high-minimum"),
        pytest.param(requirement(output_high_maximum_v=5.0), id="absolute-input-range"),
    ),
)
def test_output_low_high_and_absolute_limit_faults_fail(spec: DigitalPeerVoltageAnalysis) -> None:
    result = checks(spec)["digital-peer-voltage/spi-mosi/compatibility"]
    assert result.status == "FAIL"
    assert "Minimum margin=" in result.detail


def test_tolerant_receiver_and_exact_limit_boundaries_are_valid_controls() -> None:
    tolerant = requirement(output_high_maximum_v=5.0)
    link_data = tolerant.links[0].model_dump()
    link_data["input_limits"]["absolute_maximum_v"] = 5.5
    link_data["input_limits"]["high_minimum_v"] = 2.2
    tolerant_link = DigitalPeerVoltageLink.model_validate(link_data)
    tolerant_spec = DigitalPeerVoltageAnalysis(
        basis="Synthetic receiver explicitly rated for the driver's full range",
        links=(tolerant_link,),
    )
    assert checks(tolerant_spec)["digital-peer-voltage/spi-mosi/compatibility"].status == "PASS"

    boundary_data = tolerant.links[0].model_dump()
    boundary_data["output_limits"].update(
        {"low_maximum_v": 0.8, "high_minimum_v": 2.0, "high_maximum_v": 5.0}
    )
    boundary_data["input_limits"].update(
        {"low_maximum_v": 0.8, "high_minimum_v": 2.0, "absolute_maximum_v": 5.0}
    )
    boundary_spec = DigitalPeerVoltageAnalysis(
        basis="Synthetic exact-boundary logic limits",
        links=(DigitalPeerVoltageLink.model_validate(boundary_data),),
    )
    boundary = checks(boundary_spec)["digital-peer-voltage/spi-mosi/compatibility"]
    assert boundary.status == "PASS"
    assert boundary.observed == pytest.approx(0.0)


@pytest.mark.parametrize("fault", ("wrong-symbol", "dnp"))
def test_stale_symbol_or_dnp_pin_map_suppresses_voltage_claim(fault: str) -> None:
    result = checks(fault=fault)
    assert result["digital-peer-voltage/spi-mosi/receiver/identity"].status == "FAIL"
    assert result["digital-peer-voltage/spi-mosi/compatibility"].status == "NOT_APPLICABLE"


def test_wrong_native_net_assignment_is_localized_and_not_compared() -> None:
    result = checks(fault="wrong-net")
    pin_check = result["digital-peer-voltage/spi-mosi/receiver/pin"]
    assert pin_check.status == "FAIL"
    assert "U2.3 is assigned to OTHER" in pin_check.detail
    assert result["digital-peer-voltage/spi-mosi/compatibility"].status == "NOT_APPLICABLE"


def test_missing_limits_are_visible_as_not_configured() -> None:
    result = checks(requirement(include_limits=False))
    compatibility = result["digital-peer-voltage/spi-mosi/compatibility"]
    assert compatibility.status == "NOT_CONFIGURED"
    assert "VOL/VOH" in compatibility.detail
    assert "VIL/VIH" in compatibility.detail


def test_contract_requires_direct_distinct_endpoints_and_unique_ids() -> None:
    base = requirement().links[0]
    mismatched_map = base.model_dump()
    mismatched_map["receiver"]["net"] = "OTHER"
    with pytest.raises(ValidationError, match="same net"):
        DigitalPeerVoltageLink.model_validate(mismatched_map)
    duplicate = base.model_copy(update={"id": "SPI-MOSI"})
    with pytest.raises(ValidationError, match="IDs must be unique"):
        DigitalPeerVoltageAnalysis(basis="duplicate map guard", links=(base, duplicate))
