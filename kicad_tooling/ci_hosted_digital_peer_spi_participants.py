"""Verify native SPI pin identity and mapped peer voltage limits."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.digital_peer_voltage_models import (
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
)
from .hwrepo.digital_peer_voltages import digital_peer_voltage_checks


def verify_spi_participant_voltage(ctx: DigitalPeerFixtureContext):
    """Verify native SPI pin identity and mapped peer voltage limits."""
    expected_functions = {
        "U1.1": "SPI1_SCLK",
        "U1.2": "SPI1_COPI",
        "U1.3": "SPI1_CIPO",
        "U1.4": "SPI1_NSS",
        "U2.1": "SPI1_SCLK",
        "U2.2": "SPI1_COPI",
        "U2.3": "SPI1_CIPO",
        "U2.4": "SPI1_NSS",
    }
    ctx.observed = ctx.contracts["multi-device"]["first"]
    if ctx.observed.pin_functions != expected_functions:
        raise ValueError(
            f"Native netlist no longer preserves the exact SPI pin-function aliases: {ctx.observed.pin_functions}"
        )
    if ctx.observed.component_symbols != {"U1": "Synthetic:SPI_Node", "U2": "Synthetic:SPI_Node"}:
        raise ValueError("Native netlist changed the synthetic SPI component identities")
    if (
        ctx.normalized_hashes["multi-device"]["first"]
        != ctx.normalized_hashes["multi-device"]["repeat"]
    ):
        raise ValueError("Native SPI exports differ after normalization to the typed netlist")

    def digital_peer_limits(output_high_maximum_v: float) -> DigitalPeerVoltageAnalysis:
        basis = "Synthetic SPI controller and peripheral voltage specifications"
        return DigitalPeerVoltageAnalysis(
            basis=basis,
            links=(
                DigitalPeerVoltageLink(
                    id="spi-mosi",
                    basis="Controller MOSI directly drives the peripheral SDI pin",
                    driver=DigitalPeerPinRequirement(
                        reference="U1",
                        symbol="Synthetic:SPI_Node",
                        footprint="Synthetic:QFN",
                        pin="U1.2",
                        net="SPI_MOSI",
                    ),
                    receiver=DigitalPeerPinRequirement(
                        reference="U2",
                        symbol="Synthetic:SPI_Node",
                        footprint="Synthetic:QFN",
                        pin="U2.2",
                        net="SPI_MOSI",
                    ),
                    output_limits=DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.8,
                        high_maximum_v=output_high_maximum_v,
                        source="Synthetic controller datasheet Rev A, Table 1",
                        conditions="VDD=3.3 V, specified output load, full operating range",
                    ),
                    input_limits=DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=3.6,
                        source="Synthetic peripheral datasheet Rev B, Table 2",
                        conditions="VDD=3.3 V, full operating range",
                    ),
                ),
            ),
        )

    voltage_cases = {
        "voltage-control": (digital_peer_limits(3.3), "PASS"),
        "voltage-fault": (digital_peer_limits(5.0), "FAIL"),
    }
    for case, (spec, expected_status) in voltage_cases.items():
        by_run = {
            run: digital_peer_voltage_checks(spec, ctx.contracts["multi-device"][run])
            for run in ("first", "repeat")
        }
        if by_run["first"] != by_run["repeat"]:
            raise ValueError(f"Native SPI {case} voltage evidence changed on repeated export")
        checks = {item.id: item for item in by_run["first"]}
        compatibility = checks["digital-peer-voltage/spi-mosi/compatibility"]
        if (
            compatibility.status != expected_status
            or compatibility.observed is None
            or checks["digital-peer-voltage/spi-mosi/driver/identity"].status != "PASS"
            or (checks["digital-peer-voltage/spi-mosi/driver/pin"].status != "PASS")
            or (checks["digital-peer-voltage/spi-mosi/receiver/identity"].status != "PASS")
            or (checks["digital-peer-voltage/spi-mosi/receiver/pin"].status != "PASS")
        ):
            raise ValueError(f"Native SPI {case} voltage check lost its exact pin or limit result")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.source_hash,
            netlist_sha256=ctx.hashes["multi-device"]["first"],
            repeat_netlist_sha256=ctx.hashes["multi-device"]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes["multi-device"]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes["multi-device"]["repeat"],
            compatibility_status=compatibility.status,
            minimum_margin_v=compatibility.observed,
            driver="U1.2/SPI_MOSI",
            receiver="U2.2/SPI_MOSI",
            repeated_checks_match="true",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_electrical_checks",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )
