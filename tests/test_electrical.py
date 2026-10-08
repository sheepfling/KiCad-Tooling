"""Electrical requirements, negative engineering cases and runner evidence boundaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from kicad_tooling.hwrepo.bus_heuristics import (
    can_termination_checks,
    i2c_pullup_checks,
    spi_checks,
    usb_c_checks,
)
from kicad_tooling.hwrepo.connector_pins import similar_connector_pin_groups
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import (
    bound_inputs,
    grounding_checks,
    load_analysis,
    pin_relationship_checks,
    policy_issues,
    power_budget_checks,
    selected_config,
)
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.generation import expected_outputs
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    AnalysisPending,
    CanTerminationAnalysis,
    CanTerminationBusRequirement,
    CanTerminationEndpointRequirement,
    CanTerminationMidpointCapacitorRequirement,
    CanTerminationResistorRequirement,
    CommandEvidence,
    ComponentContract,
    ElectricalAnalysisContract,
    FrequencyAnalysis,
    GroundDomain,
    GroundingAnalysis,
    HighFrequencyAnalysis,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupElectricalWindow,
    I2cPullupInputVoltageLimit,
    I2cPullupLineRequirement,
    I2cPullupSeriesPathRequirement,
    I2cPullupSeriesResistorRequirement,
    I2cPullupVoltageCompatibilityRequirement,
    NetlistContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
    PowerAnalysis,
    PowerConnectivityAnalysis,
    PowerConnectivityRailRequirement,
    PowerLoad,
    PowerLoadConnectivityRequirement,
    PowerPinEndpointRequirement,
    PowerRail,
    PowerSourceGroupRequirement,
    ReferenceBondRequirement,
    Rs485Analysis,
    Rs485BiasResistorRequirement,
    Rs485BusRequirement,
    Rs485DnpResistorRequirement,
    Rs485EndpointPinRequirement,
    Rs485EndpointRequirement,
    Rs485InternalFailSafeRequirement,
    Rs485LocalBiasRequirement,
    Rs485NoBiasRequirement,
    Rs485RemoteBiasRequirement,
    Rs485SignalPairRequirement,
    Rs485TerminationEndpointRequirement,
    Rs485TerminationResistorRequirement,
    SerialBridgePathRequirement,
    SerialBridgeRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialExternalPeerRequirement,
    SerialLogicInputLimits,
    SerialLogicLimits,
    SerialLogicOutputLimits,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
    SerialShiftedPeerRequirement,
    SimulationMeasure,
    SpiAnalysis,
    SpiBridgePathRequirement,
    SpiBridgeRequirement,
    SpiBusRequirement,
    SpiControllerRequirement,
    SpiDeviceRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
    SpiPinNotPresent,
    SpiPinUnconnectedRequirement,
    TransientAnalysis,
    UsbCAnalysis,
    UsbCcControllerAttachment,
    UsbCcLineRequirement,
    UsbCControllerRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCProtectionAnalysis,
    UsbCProtectionComponentRequirement,
    UsbCVbusPathElement,
    UsbCVbusPathRequirement,
)
from kicad_tooling.hwrepo.power_connectivity import power_connectivity_checks
from kicad_tooling.hwrepo.return_nets import return_net_groups
from kicad_tooling.hwrepo.rs485_heuristics import rs485_checks
from kicad_tooling.hwrepo.serial_heuristics import serial_peer_checks
from kicad_tooling.hwrepo.spice import (
    expanded_deck,
    measured_checks,
    run_case,
    simulation_deck,
    simulator_version,
    waveform_checks,
)
from kicad_tooling.validate import hashes, read_netlist
from tests.support import TEMPLATE_ROOT, reference_root

PROJECT = "controller"
ISLAND = "examples/projects/controller"
NA = AnalysisNotApplicable(mode="not_applicable", reason="Synthetic test scope")


def i2c_pullup_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic local direct-resistor requirements",
        buses=(
            I2cPullupBusRequirement(
                id="control",
                basis="Reviewed synthetic controller bus requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=2_300, maximum_ohms=2_500
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
    )


def i2c_pullup_window_requirement(
    first_reference: str = "R10",
    second_reference: str = "R11",
    *,
    minimum_ohms: float = 4_000,
    maximum_ohms: float = 5_000,
    maximum_pullup_voltage_v: float = 3.3,
    maximum_low_level_voltage_v: float = 0.4,
    minimum_sink_current_ma: float = 3.0,
    maximum_bus_capacitance_pf: float = 50.0,
    maximum_rise_time_ns: float = 300.0,
) -> I2cPullupAnalysis:
    base = i2c_pullup_voltage_requirement(
        first_reference,
        second_reference,
        maximum_rail_voltage_v=maximum_pullup_voltage_v,
        maximum_input_voltage_v=maximum_pullup_voltage_v,
    )
    window = I2cPullupElectricalWindow(
        maximum_pullup_voltage_v=maximum_pullup_voltage_v,
        pullup_voltage_basis="Synthetic maximum supply tolerance",
        maximum_low_level_voltage_v=maximum_low_level_voltage_v,
        low_level_voltage_basis="Synthetic weakest-device VOL specification",
        minimum_sink_current_ma=minimum_sink_current_ma,
        sink_current_basis="Synthetic weakest-device guaranteed sink current",
        maximum_bus_capacitance_pf=maximum_bus_capacitance_pf,
        bus_capacitance_basis="Synthetic board and endpoint capacitance bound",
        maximum_rise_time_ns=maximum_rise_time_ns,
        rise_time_basis="Synthetic interface timing requirement",
    )
    bus = base.buses[0]
    sda = bus.sda.model_copy(
        update={
            "minimum_ohms": minimum_ohms,
            "maximum_ohms": maximum_ohms,
            "electrical_window": window,
        }
    )
    scl = bus.scl.model_copy(
        update={
            "minimum_ohms": minimum_ohms,
            "maximum_ohms": maximum_ohms,
            "electrical_window": window,
        }
    )
    return base.model_copy(update={"buses": (bus.model_copy(update={"sda": sda, "scl": scl}),)})


def i2c_series_pullup_requirement(
    first_reference: str = "R10", second_reference: str = "R11"
) -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic explicit series-chain pull-up requirement",
        buses=(
            I2cPullupBusRequirement(
                id="series-bus",
                basis="Synthetic reviewed controller bus requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        series_paths=(
            I2cPullupSeriesPathRequirement(
                id="sda-chain",
                basis="Synthetic reviewed discrete resistor chain",
                signal_net="I2C_SDA",
                rail_net="+3V3",
                resistors=(
                    I2cPullupSeriesResistorRequirement(
                        reference=first_reference,
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:R",
                        from_net="I2C_SDA",
                        to_net="I2C_SDA_CHAIN",
                        minimum_ohms=900,
                        maximum_ohms=1_100,
                    ),
                    I2cPullupSeriesResistorRequirement(
                        reference=second_reference,
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:R",
                        from_net="I2C_SDA_CHAIN",
                        to_net="+3V3",
                        minimum_ohms=3_500,
                        maximum_ohms=3_900,
                    ),
                ),
            ),
        ),
    )


def i2c_pullup_voltage_requirement(
    first_reference: str = "R10",
    second_reference: str = "R11",
    *,
    maximum_rail_voltage_v: float = 3.3,
    maximum_input_voltage_v: float = 3.3,
) -> I2cPullupAnalysis:
    base = i2c_series_pullup_requirement(first_reference, second_reference)

    def voltage_limit(pin: str) -> I2cPullupVoltageCompatibilityRequirement:
        return I2cPullupVoltageCompatibilityRequirement(
            input_scope_basis="Synthetic reviewed local I2C endpoint inventory",
            maximum_rail_voltage_v=maximum_rail_voltage_v,
            rail_basis="Synthetic supply ceiling including tolerance",
            input_limits=(
                I2cPullupInputVoltageLimit(
                    pin=pin,
                    expected_symbol="Synthetic:I2cTarget",
                    expected_footprint="Synthetic:SOIC8",
                    limit_kind="absolute_maximum",
                    maximum_bus_voltage_v=maximum_input_voltage_v,
                    limit_basis="Synthetic target datasheet maximum input voltage",
                ),
            ),
        )

    data = base.model_dump(mode="python")
    data["buses"][0]["sda"]["voltage_compatibility"] = voltage_limit("U1.1").model_dump()
    data["buses"][0]["scl"]["voltage_compatibility"] = voltage_limit("U1.2").model_dump()
    return I2cPullupAnalysis.model_validate(data)


def i2c_series_pullup_netlist(
    *,
    first_value: str = "1k",
    second_value: str = "3.7k",
    scl_value: str = "4.7k",
    dnp: tuple[str, ...] = (),
    extra_junction_pin: bool = False,
    first_symbol: str = "Device:R",
    second_footprint: str = "Synthetic:R",
) -> NetlistContract:
    chain_pins = ("R10.2", "R11.1", *(("U9.1",) if extra_junction_pin else ()))
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            "R10": ComponentContract(value=first_value, footprint="Synthetic:R"),
            "R11": ComponentContract(value=second_value, footprint=second_footprint),
            "R12": ComponentContract(value=scl_value, footprint="Synthetic:R"),
        },
        nets={
            "I2C_SDA": ("U1.1", "R10.1"),
            "I2C_SDA_CHAIN": chain_pins,
            "+3V3": ("R11.2", "R12.2"),
            "I2C_SCL": ("U1.2", "R12.1"),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            "R10": first_symbol,
            "R11": "Device:R",
            "R12": "Device:R",
        },
        pin_functions={
            "U1.1": "SDA",
            "U1.2": "SCL",
            "R10.1": "1",
            "R10.2": "2",
            "R11.1": "1",
            "R11.2": "2",
            "R12.1": "1",
            "R12.2": "2",
        },
        component_pin_numbers={
            "U1": ("1", "2"),
            "R10": ("1", "2"),
            "R11": ("1", "2"),
            "R12": ("1", "2"),
        },
    )


def i2c_pullup_array_requirement(
    *, unmapped_pin_reasons: dict[str, str] | None = None
) -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic reviewed resistor-array part and bus requirement",
        buses=(
            I2cPullupBusRequirement(
                id="array-bus",
                basis="Synthetic bus topology",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic reviewed array datasheet and pin-pair map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel one pin pair",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel two pin pair",
                    ),
                ),
                unmapped_pin_reasons=unmapped_pin_reasons or {},
            ),
        ),
    )


def i2c_pullup_array_netlist(
    *,
    value: str = "4x4.7k",
    symbol: str = "Synthetic:ResistorArray",
    footprint: str = "Synthetic:RA4",
    sda_signal_net: str = "I2C_SDA",
    extra_pin: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    pins = ("1", "2", "3", "4", *(("5",) if extra_pin else ()))
    nets = {
        "I2C_SDA": ("U1.1", "RN1.1") if sda_signal_net == "I2C_SDA" else ("U1.1",),
        "I2C_SCL": ("U1.2", "RN1.3"),
        "+3V3": ("RN1.2", "RN1.4"),
    }
    if sda_signal_net != "I2C_SDA":
        nets[sda_signal_net] = ("RN1.1",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            "RN1": ComponentContract(value=value, footprint=footprint),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={"U1": "Synthetic:I2cTarget", "RN1": symbol},
        pin_functions={
            "U1.1": "SDA",
            "U1.2": "SCL",
            "RN1.1": "A1",
            "RN1.2": "A2",
            "RN1.3": "B1",
            "RN1.4": "B2",
            **({"RN1.5": "NC"} if extra_pin else {}),
        },
        component_pin_numbers={"U1": ("1", "2"), "RN1": pins},
    )


def i2c_pullup_netlist(
    *,
    sda_values: tuple[str, ...] = ("4.7k", "4.7k"),
    scl_values: tuple[str, ...] = ("4.7k",),
    scl_rail: str = "+3V3",
    dnp: tuple[str, ...] = (),
    array_reference: str | None = None,
) -> NetlistContract:
    components = {
        f"R{number}": ComponentContract(value=value, footprint="")
        for number, value in enumerate((*sda_values, *scl_values), start=1)
    }
    nets: dict[str, tuple[str, ...]] = {
        "I2C_SDA": ("U1.1",),
        "I2C_SCL": ("U1.2",),
        "+3V3": (),
    }
    pin_functions = {"U1.1": "SDA", "U1.2": "SCL"}
    for index, reference in enumerate(components):
        bus_net = "I2C_SDA" if index < len(sda_values) else "I2C_SCL"
        rail_net = "+3V3" if bus_net == "I2C_SDA" else scl_rail
        nets[bus_net] = (*nets[bus_net], f"{reference}.1")
        nets[rail_net] = (*nets.get(rail_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    pin_numbers = {array_reference: ("1", "2", "3", "4")} if array_reference is not None else {}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            **{reference: "Device:R" for reference in components},
        },
        pin_functions=pin_functions,
        component_pin_numbers=pin_numbers,
    )


def spi_requirement(
    *,
    device2_miso: Literal["connected", "unconnected", "not_present"] = "connected",
    buffered_miso: bool = False,
    shared_select: bool = False,
    controller_reference: str = "U1",
    device_references: tuple[str, str] = ("U2", "U3"),
    bridge_reference: str = "U9",
    device2_symbol: str = "Synthetic:SpiPeripheral",
) -> SpiAnalysis:
    first_reference, second_reference = device_references
    miso_mode = SpiMisoConnectedRequirement(
        mode="connected",
        pin=f"{controller_reference}.3",
        net="SPI_MISO_CONTROLLER" if buffered_miso else "SPI_MISO",
    )
    device2_miso_requirement = {
        "connected": SpiMisoConnectedRequirement(
            mode="connected",
            pin=f"{second_reference}.3",
            net="SPI_MISO",
        ),
        "unconnected": SpiPinUnconnectedRequirement(
            mode="unconnected", pin=f"{second_reference}.3"
        ),
        "not_present": SpiPinNotPresent(
            mode="not_present", reason="Synthetic write-only peripheral has no MISO pin."
        ),
    }[device2_miso]
    controller = SpiControllerRequirement(
        reference=controller_reference,
        symbol="Synthetic:SpiController",
        footprint="Package_QFP:LQFP-32",
        sck=SpiPinNetRequirement(pin=f"{controller_reference}.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin=f"{controller_reference}.2", net="SPI_MOSI"),
        miso=miso_mode,
        chip_selects=(
            (SpiPinNetRequirement(pin=f"{controller_reference}.4", net="SPI_CS0"),)
            if shared_select
            else (
                SpiPinNetRequirement(pin=f"{controller_reference}.4", net="SPI_CS0"),
                SpiPinNetRequirement(pin=f"{controller_reference}.5", net="SPI_CS1"),
            )
        ),
    )
    first_miso: SpiMisoConnectedRequirement = SpiMisoConnectedRequirement(
        mode="connected",
        pin=f"{first_reference}.3",
        net="SPI_MISO_DEVICE" if buffered_miso else "SPI_MISO",
    )
    bridge = (
        (
            SpiBridgeRequirement(
                reference=bridge_reference,
                symbol="Synthetic:SpiBuffer",
                footprint="Package_SO:TSSOP-8",
                paths=(
                    SpiBridgePathRequirement(
                        signal="miso",
                        from_pin=f"{bridge_reference}.1",
                        from_net="SPI_MISO_CONTROLLER",
                        to_pin=f"{bridge_reference}.2",
                        to_net="SPI_MISO_DEVICE",
                    ),
                ),
            ),
        )
        if buffered_miso
        else ()
    )
    first_device = SpiDeviceRequirement(
        id="sensor",
        reference=first_reference,
        symbol="Synthetic:SpiPeripheral",
        footprint="Package_SO:SOIC-8",
        sck=SpiPinNetRequirement(pin=f"{first_reference}.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin=f"{first_reference}.2", net="SPI_MOSI"),
        miso=first_miso,
        chip_select=SpiPinNetRequirement(pin=f"{first_reference}.4", net="SPI_CS0"),
        shared_select_group="broadcast" if shared_select else None,
    )
    second_device = SpiDeviceRequirement(
        id="memory",
        reference=second_reference,
        symbol=device2_symbol,
        footprint="Package_SO:SOIC-8",
        sck=SpiPinNetRequirement(pin=f"{second_reference}.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin=f"{second_reference}.2", net="SPI_MOSI"),
        miso=device2_miso_requirement,
        chip_select=SpiPinNetRequirement(
            pin=f"{second_reference}.4", net="SPI_CS0" if shared_select else "SPI_CS1"
        ),
        shared_select_group="broadcast" if shared_select else None,
    )
    return SpiAnalysis(
        basis="Synthetic project-authored SPI membership and signal map",
        buses=(
            SpiBusRequirement(
                id="control",
                basis="Synthetic local SPI controller and two-device bus",
                controller=controller,
                devices=(first_device, second_device),
                bridges=bridge,
            ),
        ),
    )


def spi_netlist(spec: SpiAnalysis, *, fault: str | None = None) -> NetlistContract:
    bus = spec.buses[0]
    assignments: dict[str, str] = {}
    component_pins: dict[str, set[str]] = {}
    symbols: dict[str, str] = {}
    components: dict[str, ComponentContract] = {}

    def component(reference: str, symbol: str, footprint: str) -> None:
        components[reference] = ComponentContract(
            value=f"Synthetic {reference}", footprint=footprint
        )
        symbols[reference] = symbol
        component_pins.setdefault(reference, set())

    def add(pin: str, net: str | None) -> None:
        reference, number = pin.rsplit(".", 1)
        component_pins.setdefault(reference, set()).add(number)
        if net is not None:
            assignments[pin] = net

    controller = bus.controller
    component(controller.reference, controller.symbol, controller.footprint)
    for requirement in (controller.sck, controller.mosi, *controller.chip_selects):
        add(requirement.pin, requirement.net)
    if isinstance(controller.miso, SpiMisoConnectedRequirement):
        add(controller.miso.pin, controller.miso.net)
    elif isinstance(controller.miso, SpiPinUnconnectedRequirement):
        add(controller.miso.pin, None)

    for device in bus.devices:
        component(device.reference, device.symbol, device.footprint)
        for requirement in (device.sck, device.mosi, device.chip_select):
            add(requirement.pin, requirement.net)
        if isinstance(device.miso, SpiMisoConnectedRequirement):
            add(device.miso.pin, device.miso.net)
        elif isinstance(device.miso, SpiPinUnconnectedRequirement):
            add(device.miso.pin, None)

    for bridge in bus.bridges:
        component(bridge.reference, bridge.symbol, bridge.footprint)
        for path in bridge.paths:
            add(path.from_pin, path.from_net)
            add(path.to_pin, path.to_net)

    if fault == "device2-cs-disconnected":
        assignments.pop("U3.4", None)
    elif fault == "device2-cs-wrong-net":
        assignments["U3.4"] = "UNEXPECTED_CS"
    elif fault == "bridge-output-wrong-net":
        assignments["U9.2"] = "UNEXPECTED_MISO"

    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        component_symbols=symbols,
        component_pin_numbers={
            reference: tuple(sorted(numbers)) for reference, numbers in component_pins.items()
        },
    )


def serial_peer_requirement(
    *,
    peer_mode: Literal["direct", "level_shifted", "external"] = "direct",
    reference_policy: Literal[
        "common_net", "bonded", "separate_nets", "external_unverified", "not_applicable"
    ]
    | None = None,
    endpoint_logic_domain: str = "logic-3v3",
    peer_logic_domain: str = "logic-3v3",
    endpoint_reference: str = "U10",
    peer_reference: str = "U11",
    bridge_reference: str = "U9",
    peer_output_high_maximum_v: float = 3.3,
    peer_output_low_maximum_v: float = 0.2,
    include_logic_limits: bool = True,
) -> SerialPeerAnalysis:
    level_shifted = peer_mode == "level_shifted"
    external = peer_mode == "external"
    selected_reference_policy = reference_policy or (
        "external_unverified" if external else "separate_nets" if level_shifted else "common_net"
    )
    reference_bond = (
        ReferenceBondRequirement(
            reference="R3",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            expected_value="0R",
            side_a_pin="R3.1",
            side_b_pin="R3.2",
            side_a_net="GND_A",
            side_b_net="GND_B",
        )
        if selected_reference_policy == "bonded"
        else None
    )

    def logic_limits(
        *, output_high_maximum_v: float = 3.3, output_low_maximum_v: float = 0.2
    ) -> SerialLogicLimits:
        output_high_minimum_v = 4.2 if output_high_maximum_v > 3.6 else 3.0
        return SerialLogicLimits(
            output=SerialLogicOutputLimits(
                low_minimum_v=0.0,
                low_maximum_v=output_low_maximum_v,
                high_minimum_v=output_high_minimum_v,
                high_maximum_v=output_high_maximum_v,
                source="Synthetic UART datasheet Rev A, Table 4",
                conditions="VDD=3.3 V, specified output load, full operating range",
            ),
            input=SerialLogicInputLimits(
                absolute_minimum_v=-0.3,
                low_maximum_v=0.8,
                high_minimum_v=2.0,
                absolute_maximum_v=3.6,
                source="Synthetic UART datasheet Rev A, Table 5",
                conditions="Specified input leakage and full operating range",
            ),
        )

    endpoint = SerialEndpointRequirement(
        id="console",
        reference=endpoint_reference,
        symbol="Synthetic:UartEndpoint",
        footprint="Connector_Generic:Conn_01x03",
        logic_domain=endpoint_logic_domain,
        tx=SerialPinNetRequirement(
            pin=f"{endpoint_reference}.1", net="UART_A_TX" if level_shifted else "UART_TX"
        ),
        rx=SerialPinNetRequirement(
            pin=f"{endpoint_reference}.2", net="UART_A_RX" if level_shifted else "UART_RX"
        ),
        reference_pins=(
            (
                SerialPinNetRequirement(
                    pin=f"{endpoint_reference}.3",
                    net=(
                        "GND_A"
                        if selected_reference_policy in {"separate_nets", "bonded"}
                        else "GND"
                    ),
                ),
            )
            if selected_reference_policy != "not_applicable"
            else ()
        ),
        logic_limits=logic_limits() if include_logic_limits else None,
    )
    if external:
        peer: (
            SerialDirectPeerRequirement
            | SerialShiftedPeerRequirement
            | SerialExternalPeerRequirement
        ) = SerialExternalPeerRequirement(
            mode="external", reason="Synthetic remote device pinout has not been supplied."
        )
    else:
        peer_endpoint = SerialEndpointRequirement(
            id="device",
            reference=peer_reference,
            symbol="Synthetic:UartEndpoint",
            footprint="Connector_Generic:Conn_01x03",
            logic_domain=peer_logic_domain,
            tx=SerialPinNetRequirement(
                pin=f"{peer_reference}.1",
                net="UART_B_TX" if level_shifted else "UART_RX",
            ),
            rx=SerialPinNetRequirement(
                pin=f"{peer_reference}.2",
                net="UART_B_RX" if level_shifted else "UART_TX",
            ),
            reference_pins=(
                (
                    SerialPinNetRequirement(
                        pin=f"{peer_reference}.3",
                        net=(
                            "GND_B"
                            if selected_reference_policy in {"separate_nets", "bonded"}
                            else "GND"
                        ),
                    ),
                )
                if selected_reference_policy != "not_applicable"
                else ()
            ),
            logic_limits=(
                logic_limits(
                    output_high_maximum_v=peer_output_high_maximum_v,
                    output_low_maximum_v=peer_output_low_maximum_v,
                )
                if include_logic_limits
                else None
            ),
        )
        if level_shifted:
            bridge = SerialBridgeRequirement(
                reference=bridge_reference,
                symbol="Synthetic:UartLevelShifter",
                footprint="Package_SO:SOIC-8",
                paths=(
                    SerialBridgePathRequirement(
                        direction="a_tx_to_b_rx",
                        from_pin=f"{bridge_reference}.1",
                        from_net="UART_A_TX",
                        to_pin=f"{bridge_reference}.2",
                        to_net="UART_B_RX",
                    ),
                    SerialBridgePathRequirement(
                        direction="b_tx_to_a_rx",
                        from_pin=f"{bridge_reference}.3",
                        from_net="UART_B_TX",
                        to_pin=f"{bridge_reference}.4",
                        to_net="UART_A_RX",
                    ),
                ),
            )
            peer = SerialShiftedPeerRequirement(
                mode="level_shifted", endpoint=peer_endpoint, bridges=(bridge,)
            )
        else:
            peer = SerialDirectPeerRequirement(mode="direct", endpoint=peer_endpoint)
    return SerialPeerAnalysis(
        basis="Synthetic authored UART endpoint roles and peer map",
        links=(
            SerialPeerLinkRequirement(
                id="console-link",
                basis="Synthetic controller UART connected to one local peer",
                endpoint=endpoint,
                peer=peer,
                reference_policy=selected_reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def serial_peer_netlist(spec: SerialPeerAnalysis, *, fault: str | None = None) -> NetlistContract:
    link = spec.links[0]
    assignments: dict[str, str] = {}
    pins: dict[str, set[str]] = {}
    symbols: dict[str, str] = {}
    components: dict[str, ComponentContract] = {}
    dnp_components: set[str] = set()
    pin_electrical_types: dict[str, str] = {}

    def add_endpoint(endpoint: SerialEndpointRequirement) -> None:
        components[endpoint.reference] = ComponentContract(
            value=f"Synthetic {endpoint.id}", footprint=endpoint.footprint
        )
        symbols[endpoint.reference] = endpoint.symbol
        for mapping in (endpoint.tx, endpoint.rx, *endpoint.reference_pins):
            reference, number = mapping.pin.rsplit(".", 1)
            pins.setdefault(reference, set()).add(number)
            assignments[mapping.pin] = mapping.net

    add_endpoint(link.endpoint)
    if isinstance(link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement)):
        add_endpoint(link.peer.endpoint)
    if isinstance(link.peer, SerialShiftedPeerRequirement):
        for bridge in link.peer.bridges:
            components[bridge.reference] = ComponentContract(
                value="Synthetic UART level shifter", footprint=bridge.footprint
            )
            symbols[bridge.reference] = bridge.symbol
            for path in bridge.paths:
                for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net)):
                    reference, number = pin.rsplit(".", 1)
                    pins.setdefault(reference, set()).add(number)
                    assignments[pin] = net

    if link.reference_bond is not None and fault != "bond-missing":
        bond = link.reference_bond
        components[bond.reference] = ComponentContract(
            value=bond.expected_value,
            footprint=bond.expected_footprint,
        )
        symbols[bond.reference] = bond.expected_symbol
        pins.setdefault(bond.reference, set()).update(
            (bond.side_a_pin.rsplit(".", 1)[1], bond.side_b_pin.rsplit(".", 1)[1])
        )
        assignments[bond.side_a_pin] = bond.side_a_net
        assignments[bond.side_b_pin] = bond.side_b_net
        pin_electrical_types[bond.side_a_pin] = "passive"
        pin_electrical_types[bond.side_b_pin] = "passive"
        if fault == "bond-wrong-value":
            components[bond.reference] = components[bond.reference].model_copy(
                update={"value": "1R"}
            )
        elif fault == "bond-wrong-footprint":
            components[bond.reference] = components[bond.reference].model_copy(
                update={"footprint": "Synthetic:0402"}
            )
        elif fault == "bond-wrong-symbol":
            symbols[bond.reference] = "Device:C"
        elif fault == "bond-dnp":
            dnp_components.add(bond.reference)
        elif fault == "bond-active-pin":
            pin_electrical_types[bond.side_b_pin] = "input"
        elif fault == "bond-wrong-net":
            assignments[bond.side_b_pin] = "FLOATING_GND"

    if fault == "tx-to-tx" and isinstance(
        link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement)
    ):
        if isinstance(link.peer, SerialDirectPeerRequirement):
            assignments[link.peer.endpoint.tx.pin] = link.endpoint.tx.net
            assignments[link.peer.endpoint.rx.pin] = link.endpoint.rx.net
        else:
            assignments[link.peer.endpoint.rx.pin] = "WRONG_UART_NET"
    elif fault == "bridge-output-wrong-net" and isinstance(link.peer, SerialShiftedPeerRequirement):
        path = link.peer.bridges[0].paths[0]
        assignments[path.to_pin] = "WRONG_UART_NET"
    elif fault == "local-reference-wrong-net" and link.endpoint.reference_pins:
        assignment = link.endpoint.reference_pins[0]
        assignments[assignment.pin] = "WRONG_REFERENCE"
    elif (
        fault == "remote-reference-unconnected"
        and isinstance(link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement))
        and link.peer.endpoint.reference_pins
    ):
        assignments.pop(link.peer.endpoint.reference_pins[0].pin, None)

    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(items)) for net, items in nets.items()},
        component_symbols=symbols,
        component_pin_numbers={
            reference: tuple(sorted(numbers)) for reference, numbers in pins.items()
        },
        dnp_components=tuple(sorted(dnp_components)),
        pin_electrical_types=pin_electrical_types,
    )


def can_termination_requirement(
    first_reference: str = "R1",
    second_reference: str = "R2",
    high_pin: str = "U1.1",
    low_pin: str = "U1.2",
) -> CanTerminationAnalysis:
    return CanTerminationAnalysis(
        basis="Synthetic reviewed two-end bus topology",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=(high_pin,),
                low_pins=(low_pin,),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local-a",
                        basis="Local terminator at declared bus endpoint A",
                        topology="direct",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=first_reference,
                                first_net="CAN_H",
                                second_net="CAN_L",
                                minimum_ohms=108,
                                maximum_ohms=132,
                            ),
                        ),
                    ),
                    CanTerminationEndpointRequirement(
                        id="local-b",
                        basis="Local terminator at declared bus endpoint B",
                        topology="direct",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=second_reference,
                                first_net="CAN_H",
                                second_net="CAN_L",
                                minimum_ohms=108,
                                maximum_ohms=132,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def can_split_termination_requirement(
    first_reference: str = "R4", second_reference: str = "R5"
) -> CanTerminationAnalysis:
    """Synthetic CAN split network with an explicitly required midpoint capacitor."""
    return CanTerminationAnalysis(
        basis="Synthetic reviewed split CAN topology",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U2.1",),
                low_pins=("U2.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic split termination at the local endpoint",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=first_reference,
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference=second_reference,
                                first_net="CAN_L",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                        midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                            reference="C1",
                            expected_symbol="Synthetic:CanMidpointCapacitor",
                            expected_footprint="Synthetic:CAP",
                            midpoint_pin="C1.1",
                            reference_pin="C1.2",
                            reference_net="GND",
                            minimum_nominal_capacitance_pf=90,
                            maximum_nominal_capacitance_pf=110,
                        ),
                    ),
                ),
            ),
        ),
    )


def can_termination_netlist(
    paths: dict[str, tuple[str, str, str]] | None = None,
    *,
    dnp: tuple[str, ...] = (),
    midpoint_capacitor: tuple[str, str, str, str] | None = None,
) -> NetlistContract:
    resistor_paths = (
        {
            "R1": ("120R", "CAN_H", "CAN_L"),
            "R2": ("120R", "CAN_H", "CAN_L"),
        }
        if paths is None
        else paths
    )
    capacitor_components = (
        {}
        if midpoint_capacitor is None
        else {
            midpoint_capacitor[0]: ComponentContract(
                value=midpoint_capacitor[1], footprint="Synthetic:CAP"
            )
        }
    )
    components = {
        "U1": ComponentContract(value="Synthetic CAN transceiver", footprint=""),
        **capacitor_components,
        **{
            reference: ComponentContract(value=value, footprint="")
            for reference, (value, _, _) in resistor_paths.items()
        },
    }
    nets: dict[str, tuple[str, ...]] = {"CAN_H": ("U1.1",), "CAN_L": ("U1.2",)}
    pin_functions = {"U1.1": "CANH", "U1.2": "CANL"}
    for reference, (_, first_net, second_net) in resistor_paths.items():
        nets[first_net] = (*nets.get(first_net, ()), f"{reference}.1")
        nets[second_net] = (*nets.get(second_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    if midpoint_capacitor is not None:
        reference, _, midpoint_net, reference_net = midpoint_capacitor
        nets[midpoint_net] = (*nets.get(midpoint_net, ()), f"{reference}.1")
        nets[reference_net] = (*nets.get(reference_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:CanTransceiver",
            **({midpoint_capacitor[0]: "Device:C"} if midpoint_capacitor else {}),
            **{reference: "Device:R" for reference in resistor_paths},
        },
        pin_functions=pin_functions,
        component_pin_numbers={
            **{reference: ("1", "2") for reference in resistor_paths},
            **({midpoint_capacitor[0]: ("1", "2")} if midpoint_capacitor else {}),
        },
    )


def rs485_requirement(
    *,
    topology: Literal["two_wire_half_duplex", "four_wire_full_duplex"] = "two_wire_half_duplex",
    termination_mode: Literal["direct", "split"] = "direct",
    bias_mode: Literal["local", "remote", "internal_failsafe", "not_required"] = "local",
    isolated: bool = False,
    dnp_option: bool = False,
    external_peers: tuple[str, ...] = (),
) -> Rs485Analysis:
    pair_specs = (
        ("shared", "bidirectional", "485_LINE_1", "485_LINE_2", "R20", "R26", "R21", "R22"),
    )
    if topology == "four_wire_full_duplex":
        pair_specs = (
            (
                "board-to-peer",
                "board_to_peer",
                "485_TX_1",
                "485_TX_2",
                "R20",
                "R26",
                "R21",
                "R22",
            ),
            (
                "peer-to-board",
                "peer_to_board",
                "485_RX_1",
                "485_RX_2",
                "R23",
                "R27",
                "R24",
                "R25",
            ),
        )
    pairs: list[Rs485SignalPairRequirement] = []
    transceiver_pins: list[Rs485EndpointPinRequirement] = []
    connector_pins: list[Rs485EndpointPinRequirement] = []
    for index, (
        pair_id,
        purpose,
        line_1,
        line_2,
        term_ref,
        split_term_ref,
        up_ref,
        down_ref,
    ) in enumerate(pair_specs):
        transceiver_line_pins = (f"U20.{1 + index * 2}", f"U20.{2 + index * 2}")
        connector_line_pins = (f"J20.{1 + index * 2}", f"J20.{2 + index * 2}")
        transceiver_pins.extend(
            (
                Rs485EndpointPinRequirement(
                    role="bus_line_1",
                    pair_id=pair_id,
                    pin=transceiver_line_pins[0],
                    net=line_1,
                ),
                Rs485EndpointPinRequirement(
                    role="bus_line_2",
                    pair_id=pair_id,
                    pin=transceiver_line_pins[1],
                    net=line_2,
                ),
            )
        )
        connector_pins.extend(
            (
                Rs485EndpointPinRequirement(
                    role="bus_line_1", pair_id=pair_id, pin=connector_line_pins[0], net=line_1
                ),
                Rs485EndpointPinRequirement(
                    role="bus_line_2", pair_id=pair_id, pin=connector_line_pins[1], net=line_2
                ),
            )
        )
        if bias_mode == "local":
            bias: (
                Rs485LocalBiasRequirement
                | Rs485RemoteBiasRequirement
                | Rs485InternalFailSafeRequirement
                | Rs485NoBiasRequirement
            ) = Rs485LocalBiasRequirement(
                mode="local",
                basis="Synthetic two-resistor idle-bus bias values authored for this fixture",
                pull_up=Rs485BiasResistorRequirement(
                    reference=up_ref,
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    bus_net=line_1,
                    rail_net="+5V_BIAS",
                    minimum_ohms=600,
                    maximum_ohms=750,
                ),
                pull_down=Rs485BiasResistorRequirement(
                    reference=down_ref,
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    bus_net=line_2,
                    rail_net="GND_BUS",
                    minimum_ohms=600,
                    maximum_ohms=750,
                ),
            )
        elif bias_mode == "remote":
            bias = Rs485RemoteBiasRequirement(
                mode="remote",
                basis="Synthetic remote node provides bus-idle bias",
                reason="Bias resistors are fitted in the remote master assembly.",
            )
        elif bias_mode == "internal_failsafe":
            bias = Rs485InternalFailSafeRequirement(
                mode="internal_failsafe",
                basis="Synthetic reviewed transceiver specification states receiver failsafe",
                transceiver_references=("U20",),
            )
        else:
            bias = Rs485NoBiasRequirement(
                mode="not_required",
                basis="Synthetic board has no local bus-idle bias requirement",
                reason="The deployed system contract covers idle-bus handling externally.",
            )
        if termination_mode == "split":
            midpoint = f"TERM_{pair_id.upper().replace('-', '_')}"
            termination = Rs485TerminationEndpointRequirement(
                id="local-end",
                basis="Two authored resistor legs form the local split termination",
                topology="split",
                midpoint_net=midpoint,
                resistors=(
                    Rs485TerminationResistorRequirement(
                        reference=term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_1,
                        second_net=midpoint,
                        minimum_ohms=57,
                        maximum_ohms=63,
                    ),
                    Rs485TerminationResistorRequirement(
                        reference=split_term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_2,
                        second_net=midpoint,
                        minimum_ohms=57,
                        maximum_ohms=63,
                    ),
                ),
            )
        else:
            termination = Rs485TerminationEndpointRequirement(
                id="local-end",
                basis="Fitted local endpoint termination",
                topology="direct",
                resistors=(
                    Rs485TerminationResistorRequirement(
                        reference=term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_1,
                        second_net=line_2,
                        minimum_ohms=117,
                        maximum_ohms=123,
                    ),
                ),
            )
        remote_termination = Rs485TerminationEndpointRequirement(
            id="remote-end",
            basis="Remote cable endpoint termination is owned by the remote assembly",
            topology="external",
        )
        if dnp_option:
            termination_data = remote_termination.model_dump(mode="python")
            termination_data["expected_dnp_resistors"] = (
                Rs485DnpResistorRequirement(
                    reference="R28",
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    first_net=line_1,
                    second_net=line_2,
                ).model_dump(mode="python"),
            )
            remote_termination = Rs485TerminationEndpointRequirement.model_validate(
                termination_data
            )
        pairs.append(
            Rs485SignalPairRequirement(
                id=pair_id,
                basis="Synthetic project-declared pair mapping",
                purpose=purpose,
                line_1_net=line_1,
                line_2_net=line_2,
                terminations=(termination, remote_termination),
                bias=bias,
            )
        )
    transceiver_pins.extend(
        (
            Rs485EndpointPinRequirement(role="driver_input", pin="U20.5", net="UART_TX"),
            Rs485EndpointPinRequirement(role="receiver_output", pin="U20.6", net="UART_RX"),
            Rs485EndpointPinRequirement(role="driver_enable", pin="U20.7", net="BUS_DIR"),
            Rs485EndpointPinRequirement(role="receiver_enable", pin="U20.8", net="BUS_DIR"),
            Rs485EndpointPinRequirement(
                role="reference", pin="U20.9", net="GND_LOGIC" if isolated else "GND_BUS"
            ),
        )
    )
    if isolated:
        transceiver_pins.append(
            Rs485EndpointPinRequirement(role="reference", pin="U20.10", net="GND_BUS")
        )
    connector_pins.append(Rs485EndpointPinRequirement(role="reference", pin="J20.9", net="GND_BUS"))
    return Rs485Analysis(
        basis="Synthetic authored RS-485 topology, transceiver map, and termination/bias intent",
        buses=(
            Rs485BusRequirement(
                id="fieldbus",
                basis="Synthetic RS-485 bus topology and local endpoint",
                topology=topology,
                pairs=tuple(pairs),
                endpoints=(
                    Rs485EndpointRequirement(
                        id="controller",
                        kind="transceiver",
                        reference="U20",
                        symbol="Synthetic:Rs485Transceiver",
                        footprint="Package_SO:SOIC-16",
                        pins=tuple(transceiver_pins),
                    ),
                    Rs485EndpointRequirement(
                        id="bus-connector",
                        kind="connector",
                        reference="J20",
                        symbol="Synthetic:Rs485Connector",
                        footprint="Connector_Generic:Conn_01x09",
                        pins=tuple(connector_pins),
                    ),
                ),
                external_peers=external_peers,
            ),
        ),
    )


def rs485_netlist(
    spec: Rs485Analysis,
    *,
    fault: Literal[
        "endpoint-line-wrong-net",
        "endpoint-reference-wrong-net",
        "termination-dnp",
        "termination-wrong-net",
        "bias-dnp",
        "bias-wrong-net",
        "dnp-option-fitted",
        "identity-wrong",
    ]
    | None = None,
) -> NetlistContract:
    assignments: dict[str, str] = {}
    components: dict[str, ComponentContract] = {}
    symbols: dict[str, str] = {}
    pin_numbers: dict[str, set[str]] = {}
    pin_functions: dict[str, str] = {}
    dnp: set[str] = set()

    def add_pin(pin: str, net: str, role: str) -> None:
        reference, number = pin.rsplit(".", 1)
        pin_numbers.setdefault(reference, set()).add(number)
        pin_functions[pin] = role
        assignments[pin] = net

    resistor_values: dict[str, tuple[str, str, str, str]] = {}
    for bus in spec.buses:
        for endpoint in bus.endpoints:
            components[endpoint.reference] = ComponentContract(
                value=f"Synthetic {endpoint.kind}", footprint=endpoint.footprint
            )
            symbols[endpoint.reference] = endpoint.symbol
            for pin in endpoint.pins:
                add_pin(pin.pin, pin.net, pin.role)
        for pair in bus.pairs:
            for endpoint in pair.terminations:
                for resistor in endpoint.resistors:
                    resistor_values[resistor.reference] = (
                        f"{(resistor.minimum_ohms + resistor.maximum_ohms) / 2:g}R",
                        resistor.first_net,
                        resistor.second_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
                for resistor in endpoint.expected_dnp_resistors:
                    resistor_values[resistor.reference] = (
                        "120R",
                        resistor.first_net,
                        resistor.second_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
                    dnp.add(resistor.reference)
            if isinstance(pair.bias, Rs485LocalBiasRequirement):
                for resistor in (pair.bias.pull_up, pair.bias.pull_down):
                    resistor_values[resistor.reference] = (
                        "680R",
                        resistor.bus_net,
                        resistor.rail_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
    for reference, (value, first_net, second_net, footprint) in resistor_values.items():
        components[reference] = ComponentContract(value=value, footprint=footprint)
        pin_numbers[reference] = {"1", "2"}
        pin_functions[f"{reference}.1"] = "1"
        pin_functions[f"{reference}.2"] = "2"
        assignments[f"{reference}.1"] = first_net
        assignments[f"{reference}.2"] = second_net

    if fault == "endpoint-line-wrong-net":
        assignments["U20.1"] = "WRONG_PAIR"
    elif fault == "endpoint-reference-wrong-net":
        assignments["J20.9"] = "GND_OTHER"
    elif fault == "termination-dnp":
        dnp.add("R20")
    elif fault == "termination-wrong-net":
        assignments["R20.2"] = "WRONG_PAIR"
    elif fault == "bias-dnp":
        dnp.add("R21")
    elif fault == "bias-wrong-net":
        assignments["R22.2"] = "WRONG_REFERENCE"
    elif fault == "identity-wrong":
        symbols["U20"] = "Synthetic:DifferentTransceiver"
    elif fault == "dnp-option-fitted":
        dnp.discard("R28")

    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        dnp_components=tuple(sorted(dnp)),
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers={
            reference: tuple(sorted(numbers)) for reference, numbers in pin_numbers.items()
        },
    )


def power_connectivity_requirement(
    *, source_selection: Literal["all", "any"] = "all"
) -> PowerConnectivityAnalysis:
    source_endpoints = (
        PowerPinEndpointRequirement(
            id="barrel-input",
            reference="J40",
            symbol="Synthetic:PowerInput",
            footprint="Connector_BarrelJack:BarrelJack_Horizontal",
            pins=("J40.1",),
        ),
        PowerPinEndpointRequirement(
            id="terminal-input",
            reference="J41",
            symbol="Synthetic:PowerInput",
            footprint="Connector_Generic:Conn_01x02",
            pins=("J41.1",),
        ),
    )
    return PowerConnectivityAnalysis(
        basis="Synthetic reviewed source and load pin map",
        rails=(
            PowerConnectivityRailRequirement(
                id="supply",
                basis="Reviewed unregulated input rail",
                net="VIN_IN",
                source_groups=(
                    PowerSourceGroupRequirement(
                        id="approved-inputs",
                        basis="At least one approved input connector is populated",
                        selection=source_selection,
                        endpoints=source_endpoints,
                    ),
                ),
                loads=(
                    PowerLoadConnectivityRequirement(
                        id="load",
                        basis="Budgeted input load includes regulator and monitor pins",
                        endpoints=(
                            PowerPinEndpointRequirement(
                                id="regulator",
                                reference="U40",
                                symbol="Synthetic:PowerRegulator",
                                footprint="Package_SO:SOIC-8",
                                pins=("U40.1",),
                            ),
                            PowerPinEndpointRequirement(
                                id="monitor",
                                reference="U41",
                                symbol="Synthetic:VoltageMonitor",
                                footprint="Package_SOT:SOT-23-5",
                                pins=("U41.1",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def power_connectivity_netlist(
    *,
    fault: Literal[
        "source-wrong-net",
        "load-wrong-net",
        "source-dnp",
        "all-sources-dnp",
        "source-identity-wrong",
    ]
    | None = None,
) -> NetlistContract:
    components = {
        "J40": ComponentContract(
            value="Synthetic barrel input", footprint="Connector_BarrelJack:BarrelJack_Horizontal"
        ),
        "J41": ComponentContract(
            value="Synthetic terminal input", footprint="Connector_Generic:Conn_01x02"
        ),
        "U40": ComponentContract(value="Synthetic regulator", footprint="Package_SO:SOIC-8"),
        "U41": ComponentContract(value="Synthetic monitor", footprint="Package_SOT:SOT-23-5"),
    }
    symbols = {
        "J40": "Synthetic:PowerInput",
        "J41": "Synthetic:PowerInput",
        "U40": "Synthetic:PowerRegulator",
        "U41": "Synthetic:VoltageMonitor",
    }
    assignments = {
        "J40.1": "VIN_IN",
        "J41.1": "VIN_IN",
        "U40.1": "VIN_IN",
        "U41.1": "VIN_IN",
    }
    dnp: set[str] = set()
    if fault == "source-wrong-net":
        assignments["J40.1"] = "WRONG_INPUT"
    elif fault == "load-wrong-net":
        assignments["U40.1"] = "WRONG_INPUT"
    elif fault == "source-dnp":
        dnp.add("J40")
    elif fault == "all-sources-dnp":
        dnp.update(("J40", "J41"))
    elif fault == "source-identity-wrong":
        symbols["J40"] = "Synthetic:DifferentConnector"
    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        dnp_components=tuple(sorted(dnp)),
        component_symbols=symbols,
        pin_functions={pin: pin.rsplit(".", 1)[1] for pin in assignments},
        component_pin_numbers={reference: ("1",) for reference in components},
    )


def usb_c_requirement(
    *,
    role: Literal["source", "sink", "dual_role", "debug_accessory"] = "source",
    controller: bool = False,
    connector: str = "J1",
    board_component: str = "U1",
    controller_reference: str = "U2",
    protection_reference: str = "D1",
    resistor_references: tuple[str, str] = ("R1", "R2"),
    vbus_path: bool = False,
) -> UsbCAnalysis:
    cc1_attachment = (
        UsbCcControllerAttachment(kind="controller", controller_pin=f"{controller_reference}.5")
        if controller
        else UsbCcResistorAttachment(
            kind="resistor",
            behavior="rd" if role == "sink" else "rp",
            reference=resistor_references[0],
            rail_net="GND" if role == "sink" else "+5V",
            minimum_ohms=5_000 if role == "sink" else 50_000,
            maximum_ohms=5_200 if role == "sink" else 60_000,
        )
    )
    cc2_attachment = (
        UsbCcControllerAttachment(kind="controller", controller_pin=f"{controller_reference}.6")
        if controller
        else UsbCcResistorAttachment(
            kind="resistor",
            behavior="rd" if role == "sink" else "rp",
            reference=resistor_references[1],
            rail_net="GND" if role == "sink" else "+5V",
            minimum_ohms=5_000 if role == "sink" else 50_000,
            maximum_ohms=5_200 if role == "sink" else 60_000,
        )
    )
    return UsbCAnalysis(
        basis="Synthetic USB-C port role and pinout requirements",
        ports=(
            UsbCPortRequirement(
                id="host-port",
                basis="Reviewed synthetic receptacle role and pinout",
                connector=connector,
                role=role,
                cc1=UsbCcLineRequirement(
                    connector_pin=f"{connector}.4", net="CC1", attachment=cc1_attachment
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin=f"{connector}.5", net="CC2", attachment=cc2_attachment
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin=f"{connector}.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin=f"{board_component}.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=(
                    f"{connector}.2",
                    f"{connector}.3",
                    f"{board_component}.5",
                ),
                source_rail="+5V" if role == "source" and not controller else None,
                controller=(
                    UsbCControllerRequirement(
                        reference=controller_reference,
                        symbol="Synthetic:TypeCController",
                        footprint="Package_QFN:QFN-16",
                    )
                    if controller
                    else None
                ),
                vbus_path=(
                    UsbCVbusPathRequirement(
                        id="input-path",
                        basis="Synthetic reviewed connector-to-system VBUS path",
                        connector_pin=f"{connector}.1",
                        connector_net="VBUS_PORT",
                        board_pin=f"{board_component}.1",
                        board_net="VBUS_SYSTEM",
                        elements=(
                            UsbCVbusPathElement(
                                reference="F1",
                                symbol="Device:Fuse",
                                footprint="Fuse:Fuse_1206_3216Metric",
                                port_side_net="VBUS_PORT",
                                system_side_net="VBUS_FUSED",
                                port_side_pins=("F1.1",),
                                system_side_pins=("F1.2",),
                                pin_assignments=(
                                    UsbCNetPinAssignment(pin="F1.1", net="VBUS_PORT"),
                                    UsbCNetPinAssignment(pin="F1.2", net="VBUS_FUSED"),
                                ),
                            ),
                            UsbCVbusPathElement(
                                reference="U3",
                                symbol="Synthetic:LoadSwitch",
                                footprint="Package_DFN:DFN-6",
                                port_side_net="VBUS_FUSED",
                                system_side_net="VBUS_SYSTEM",
                                port_side_pins=("U3.1", "U3.2"),
                                system_side_pins=("U3.3",),
                                pin_assignments=(
                                    UsbCNetPinAssignment(pin="U3.1", net="VBUS_FUSED"),
                                    UsbCNetPinAssignment(pin="U3.2", net="VBUS_FUSED"),
                                    UsbCNetPinAssignment(pin="U3.3", net="VBUS_SYSTEM"),
                                    UsbCNetPinAssignment(pin="U3.4", net="SWITCH_ENABLE"),
                                ),
                            ),
                        ),
                    )
                    if vbus_path
                    else None
                ),
                protection=UsbCProtectionAnalysis(
                    basis="Synthetic reviewed CC ESD part and pin assignments",
                    components=(
                        UsbCProtectionComponentRequirement(
                            reference=protection_reference,
                            symbol="Synthetic:UsbProtection",
                            footprint="Package_DFN:DFN-6",
                            pins=(
                                UsbCNetPinAssignment(pin=f"{protection_reference}.1", net="CC1"),
                                UsbCNetPinAssignment(pin=f"{protection_reference}.2", net="GND"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def usb_c_netlist(
    *,
    role: Literal["source", "sink", "dual_role", "debug_accessory"] = "source",
    controller: bool = False,
    dnp: tuple[str, ...] = (),
    footprint: str = "Package_DFN:DFN-6",
    connector: str = "J1",
    board_component: str = "U1",
    controller_reference: str = "U2",
    protection_reference: str = "D1",
    resistor_references: tuple[str, str] = ("R1", "R2"),
    vbus_path: bool = False,
) -> NetlistContract:
    components = {
        connector: ComponentContract(value="Synthetic USB-C receptacle", footprint=""),
        board_component: ComponentContract(value="Synthetic system connector", footprint=""),
        protection_reference: ComponentContract(value="Synthetic protection", footprint=footprint),
    }
    symbols = {
        connector: "Synthetic:UsbCReceptacle",
        board_component: "Synthetic:SystemConnector",
        protection_reference: "Synthetic:UsbProtection",
    }
    nets: dict[str, tuple[str, ...]] = {
        "CC1": (f"{connector}.4", f"{protection_reference}.1"),
        "CC2": (f"{connector}.5",),
        "VBUS_PORT": (f"{connector}.1",),
        "VBUS_SYSTEM": (f"{board_component}.1",),
        "GND": (
            f"{connector}.2",
            f"{connector}.3",
            f"{board_component}.5",
            f"{protection_reference}.2",
        ),
    }
    pin_functions = {
        f"{connector}.1": "VBUS",
        f"{connector}.2": "GND",
        f"{connector}.3": "GND",
        f"{connector}.4": "CC1",
        f"{connector}.5": "CC2",
        f"{board_component}.1": "VBUS",
        f"{board_component}.5": "GND",
        f"{protection_reference}.1": "CC1",
        f"{protection_reference}.2": "GND",
    }
    pin_numbers = {
        connector: ("1", "2", "3", "4", "5"),
        board_component: ("1", "5"),
        protection_reference: ("1", "2"),
    }
    if vbus_path:
        components.update(
            {
                "F1": ComponentContract(value="PTC fuse", footprint="Fuse:Fuse_1206_3216Metric"),
                "U3": ComponentContract(
                    value="Synthetic load switch", footprint="Package_DFN:DFN-6"
                ),
            }
        )
        symbols.update({"F1": "Device:Fuse", "U3": "Synthetic:LoadSwitch"})
        nets["VBUS_PORT"] = (*nets["VBUS_PORT"], "F1.1")
        nets["VBUS_FUSED"] = ("F1.2", "U3.1", "U3.2")
        nets["VBUS_SYSTEM"] = (*nets["VBUS_SYSTEM"], "U3.3")
        nets["SWITCH_ENABLE"] = ("U3.4",)
        pin_functions.update(
            {
                "F1.1": "1",
                "F1.2": "2",
                "U3.1": "VIN",
                "U3.2": "VIN_ALT",
                "U3.3": "VOUT",
                "U3.4": "EN",
            }
        )
        pin_numbers.update({"F1": ("1", "2"), "U3": ("1", "2", "3", "4", "5", "6")})
    if controller:
        components[controller_reference] = ComponentContract(
            value="Synthetic USB-C controller", footprint="Package_QFN:QFN-16"
        )
        symbols[controller_reference] = "Synthetic:TypeCController"
        nets["CC1"] = (*nets["CC1"], f"{controller_reference}.5")
        nets["CC2"] = (*nets["CC2"], f"{controller_reference}.6")
        pin_functions.update(
            {f"{controller_reference}.5": "CC1", f"{controller_reference}.6": "CC2"}
        )
        pin_numbers[controller_reference] = tuple(str(index) for index in range(1, 17))
    else:
        first_resistor, second_resistor = resistor_references
        resistor_value = "5.1k" if role == "sink" else "56k"
        components.update(
            {
                first_resistor: ComponentContract(
                    value=resistor_value, footprint="Synthetic:R_0603"
                ),
                second_resistor: ComponentContract(
                    value=resistor_value, footprint="Synthetic:R_0603"
                ),
            }
        )
        symbols.update({first_resistor: "Device:R", second_resistor: "Device:R"})
        nets["CC1"] = (*nets["CC1"], f"{first_resistor}.1")
        nets["CC2"] = (*nets["CC2"], f"{second_resistor}.1")
        resistor_rail = "GND" if role == "sink" else "+5V"
        nets[resistor_rail] = (
            *nets.get(resistor_rail, ()),
            f"{first_resistor}.2",
            f"{second_resistor}.2",
        )
        pin_functions.update(
            {
                f"{first_resistor}.1": "1",
                f"{first_resistor}.2": "2",
                f"{second_resistor}.1": "1",
                f"{second_resistor}.2": "2",
            }
        )
        pin_numbers.update({first_resistor: ("1", "2"), second_resistor: ("1", "2")})
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers=pin_numbers,
    )


def install_fixture(root: Path, version: str = "47") -> ElectricalAnalysisContract:
    """Author synthetic requirements only in a disposable copy of the training island."""
    directory = root / ISLAND / "tests/electrical"
    directory.mkdir(parents=True)
    for name in ("startup.cir", "signal.cir"):
        shutil.copy2(TEMPLATE_ROOT / "templates/electrical" / name, directory / name)
    config = selected_config(root, PROJECT)
    source = hashes(root, config.source_roots)

    def model(name: str) -> dict[str, str]:
        path = directory / name
        return {path.relative_to(root).as_posix(): digest(path)}

    startup_model = model("startup.cir")
    signal_model = model("signal.cir")
    startup = TransientAnalysis(
        id="startup",
        basis="Synthetic 5 V source ramp into 100 uF through 1 ohm",
        deck=next(iter(startup_model)),
        source_sha256=source,
        model_sha256=startup_model,
        step_s=1e-6,
        stop_s=0.005,
        measures=(
            SimulationMeasure(
                id="peak-current",
                expression="-i(vrail)",
                statistic="max",
                unit="A",
                start=0.0,
                stop=0.001,
                maximum=5.1,
            ),
        ),
    )
    steady = startup.model_copy(
        update={
            "id": "steady-state",
            "measures": (
                SimulationMeasure(
                    id="average-current",
                    expression="-i(vrail)",
                    statistic="avg",
                    unit="A",
                    start=0.004,
                    stop=0.005,
                    minimum=0.049,
                    maximum=0.051,
                ),
                SimulationMeasure(
                    id="average-power",
                    expression="-v(supply)*i(vrail)",
                    statistic="avg",
                    unit="W",
                    start=0.004,
                    stop=0.005,
                    minimum=0.24,
                    maximum=0.26,
                ),
                SimulationMeasure(
                    id="rail-minimum",
                    expression="v(out)",
                    statistic="min",
                    unit="V",
                    start=0.004,
                    stop=0.005,
                    minimum=4.9,
                ),
            ),
        }
    )
    sweep = FrequencyAnalysis(
        id="passband",
        basis="Synthetic 50 ohm/10 pF first-order low-pass",
        deck=next(iter(signal_model)),
        source_sha256=source,
        model_sha256=signal_model,
        start_hz=1000.0,
        stop_hz=1e9,
        measures=(
            SimulationMeasure(
                id="gain",
                expression="db(v(out)/v(in))",
                statistic="min",
                unit="dB",
                start=1000.0,
                stop=1e6,
                minimum=-0.1,
                maximum=0.0,
            ),
        ),
    )
    waveform = TransientAnalysis(
        id="edges",
        basis="Synthetic 1 MHz source with 1 ns rise and fall times",
        deck=sweep.deck,
        source_sha256=source,
        model_sha256=signal_model,
        step_s=1e-10,
        stop_s=3e-6,
        measures=(
            SimulationMeasure(
                id="overshoot",
                expression="v(out)",
                statistic="max",
                unit="V",
                start=0.0,
                stop=3e-6,
                minimum=0.99,
                maximum=1.01,
            ),
        ),
    )
    contract = ElectricalAnalysisContract(
        project_id=PROJECT,
        ngspice_version=version,
        grounding=GroundingAnalysis(
            basis="Synthetic reference net, not protective earth",
            domains=(GroundDomain(net="PILOT_B", pins=("R1.2", "R2.2")),),
        ),
        pcb_return_paths=NA,
        power=PowerAnalysis(
            rails=(
                PowerRail(
                    id="supply",
                    basis="Synthetic derated supply and path limits",
                    voltage_v=5.0,
                    continuous_limit_a=0.1,
                    peak_limit_a=6.0,
                    peak_duration_limit_s=0.002,
                    loads=(
                        PowerLoad(
                            id="load",
                            basis="Synthetic worst case",
                            steady_a=0.05,
                            startup_a=5.0,
                            startup_s=0.001,
                        ),
                    ),
                ),
            ),
            startup=(startup,),
            steady_state=(steady,),
        ),
        high_frequency=HighFrequencyAnalysis(
            basis="Synthetic model only",
            frequency_hz=1e6,
            rise_time_s=1e-9,
            sweeps=(sweep,),
            waveforms=(waveform,),
        ),
        test_access=NA,
    )
    path = root / ISLAND / "tests/electrical.json"
    write_model(path, contract)
    test_path = root / ISLAND / "tests/contract.json"
    raw = json.loads(test_path.read_text())
    raw["electrical"] = "tests/electrical.json"
    test_path.write_text(json.dumps(raw))
    return contract


class ElectricalTests(unittest.TestCase):
    def stage(self) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="electrical-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "repository"
        shutil.copytree(reference_root(), root)
        return root

    def ground(self) -> tuple[GroundingAnalysis, NetlistContract]:
        spec = GroundingAnalysis(
            basis="Independent pin requirements",
            domains=(
                GroundDomain(net="GND", pins=("U1.2", "J1.2")),
                GroundDomain(net="AGND", pins=("U2.2",)),
            ),
        )
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="fixture", footprint="") for ref in ("U1", "U2", "J1")
            },
            nets={"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",)},
        )
        return spec, observed

    def test_i2c_pullup_contract_checks_exact_rail_and_nominal_parallel_range(self) -> None:
        checks = {
            item.id: item
            for item in i2c_pullup_checks(i2c_pullup_requirement(), i2c_pullup_netlist())
        }
        self.assertEqual(checks["i2c-pullup/control/sda"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/control/sda"].observed, 2_350)
        self.assertEqual(checks["i2c-pullup/control/scl"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/control/scl"].observed, 4_700)

        low = i2c_pullup_netlist(sda_values=("1k", "1k"))
        checks = {item.id: item for item in i2c_pullup_checks(i2c_pullup_requirement(), low)}
        self.assertEqual(checks["i2c-pullup/control/sda"].status, "FAIL")
        self.assertEqual(checks["i2c-pullup/control/sda"].observed, 500)
        self.assertIn("R1=1000Ω, R2=1000Ω", checks["i2c-pullup/control/sda"].detail)

        wrong_rail = i2c_pullup_netlist(scl_rail="+5V")
        checks = {item.id: item for item in i2c_pullup_checks(i2c_pullup_requirement(), wrong_rail)}
        self.assertEqual(checks["i2c-pullup/control/scl"].status, "FAIL")
        self.assertIn("unexpected direct pull-ups to +5V", checks["i2c-pullup/control/scl"].detail)

    def test_i2c_pullup_electrical_window_checks_authored_current_and_rise_time_bounds(
        self,
    ) -> None:
        passing = {
            item.id: item
            for item in i2c_pullup_checks(
                i2c_pullup_window_requirement(), i2c_series_pullup_netlist()
            )
        }
        minimum_id = "i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance"
        maximum_id = "i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance"
        self.assertEqual(passing[minimum_id].status, "PASS")
        self.assertEqual(passing[minimum_id].observed, 4_000)
        self.assertIn("966.667Ω", passing[minimum_id].detail)
        self.assertEqual(passing[maximum_id].status, "PASS")
        self.assertEqual(passing[maximum_id].observed, 5_000)
        self.assertIn("7081.32Ω", passing[maximum_id].detail)

        lower_boundary = {
            item.id: item
            for item in i2c_pullup_checks(
                i2c_pullup_window_requirement(
                    minimum_ohms=1_000,
                    maximum_ohms=5_000,
                    maximum_pullup_voltage_v=3.4,
                    maximum_bus_capacitance_pf=100.0,
                    maximum_rise_time_ns=423.65,
                ),
                i2c_series_pullup_netlist(),
            )
        }
        self.assertEqual(lower_boundary[minimum_id].status, "PASS")
        self.assertEqual(lower_boundary[maximum_id].status, "PASS")

        outside_both_bounds = {
            item.id: item
            for item in i2c_pullup_checks(
                i2c_pullup_window_requirement(
                    minimum_ohms=900,
                    maximum_ohms=3_600,
                    maximum_bus_capacitance_pf=100.0,
                ),
                i2c_series_pullup_netlist(),
            )
        }
        self.assertEqual(outside_both_bounds[minimum_id].status, "FAIL")
        self.assertEqual(outside_both_bounds[maximum_id].status, "FAIL")

    def test_i2c_pullup_electrical_window_reports_infeasible_inputs(self) -> None:
        checks = {
            item.id: item
            for item in i2c_pullup_checks(
                i2c_pullup_window_requirement(
                    maximum_pullup_voltage_v=5.0,
                    minimum_sink_current_ma=1.0,
                    maximum_bus_capacitance_pf=300.0,
                    maximum_rise_time_ns=100.0,
                ),
                i2c_series_pullup_netlist(),
            )
        }
        for line in ("sda", "scl"):
            related = [
                item
                for item in checks.values()
                if item.id.startswith(f"i2c-pullup/series-bus/{line}/electrical-window/")
            ]
            self.assertEqual(len(related), 2)
            self.assertTrue(all(item.status == "FAIL" for item in related))
            self.assertTrue(
                all("derived resistor window is empty" in item.detail for item in related)
            )

        valid_window = i2c_pullup_window_requirement().buses[0].sda.electrical_window
        assert valid_window is not None
        invalid_window = valid_window.model_dump()
        invalid_window["maximum_pullup_voltage_v"] = valid_window.maximum_low_level_voltage_v
        with self.assertRaisesRegex(ValueError, "must exceed"):
            I2cPullupElectricalWindow.model_validate(invalid_window)

    def test_i2c_pullup_voltage_compatibility_checks_authored_limits_and_native_pins(self) -> None:
        observed = i2c_series_pullup_netlist()
        specification = i2c_pullup_voltage_requirement()
        checks = {item.id: item for item in i2c_pullup_checks(specification, observed)}
        sda_id = "i2c-pullup/series-bus/sda/voltage-compatibility"
        scl_id = "i2c-pullup/series-bus/scl/voltage-compatibility"
        self.assertEqual(checks[sda_id].status, "PASS")
        self.assertEqual(checks[sda_id].observed, 3.3)
        self.assertEqual(checks[scl_id].status, "PASS")
        self.assertIn("exact native symbol, footprint, pin inventory", checks[sda_id].detail)

        excessive_rail = i2c_pullup_voltage_requirement(maximum_input_voltage_v=3.2)
        high_checks = {item.id: item for item in i2c_pullup_checks(excessive_rail, observed)}
        self.assertEqual(high_checks[sda_id].status, "FAIL")
        self.assertIn(
            "maximum 3.3 V exceeds U1.1 maximum bus voltage 3.2 V", high_checks[sda_id].detail
        )
        self.assertIn(
            "Synthetic target datasheet maximum input voltage", high_checks[sda_id].detail
        )

        wrong_net = observed.model_copy(
            update={
                "nets": {
                    **{
                        net: tuple(pin for pin in pins if pin != "U1.1")
                        for net, pins in observed.nets.items()
                    },
                    "WRONG_SDA": ("U1.1",),
                }
            }
        )
        wrong_net_checks = {item.id: item for item in i2c_pullup_checks(specification, wrong_net)}
        self.assertEqual(wrong_net_checks[sda_id].status, "FAIL")
        self.assertIn(
            "U1.1 is assigned to WRONG_SDA; expected only I2C_SDA", wrong_net_checks[sda_id].detail
        )

        wrong_identity = observed.model_copy(
            update={"component_symbols": {**observed.component_symbols, "U1": "Synthetic:Other"}}
        )
        identity_checks = {
            item.id: item for item in i2c_pullup_checks(specification, wrong_identity)
        }
        self.assertEqual(identity_checks[sda_id].status, "FAIL")
        self.assertIn("U1 symbol is Synthetic:Other", identity_checks[sda_id].detail)

        missing_pin = observed.model_copy(
            update={
                "component_pin_numbers": {
                    **observed.component_pin_numbers,
                    "U1": ("2",),
                }
            }
        )
        inventory_checks = {item.id: item for item in i2c_pullup_checks(specification, missing_pin)}
        self.assertEqual(inventory_checks[sda_id].status, "FAIL")
        self.assertIn(
            "U1.1 is absent from the native pin inventory", inventory_checks[sda_id].detail
        )

        dnp_target = observed.model_copy(update={"dnp_components": ("U1",)})
        dnp_checks = {item.id: item for item in i2c_pullup_checks(specification, dnp_target)}
        self.assertEqual(dnp_checks[sda_id].status, "FAIL")
        self.assertIn("U1 is DNP", dnp_checks[sda_id].detail)

        unconfigured = {
            item.id for item in i2c_pullup_checks(i2c_series_pullup_requirement(), observed)
        }
        self.assertNotIn(sda_id, unconfigured)

    def test_i2c_pullup_voltage_compatibility_contract_rejects_duplicate_pins(self) -> None:
        limit = I2cPullupInputVoltageLimit(
            pin="U1.1",
            expected_symbol="Synthetic:I2cTarget",
            expected_footprint="Synthetic:SOIC8",
            limit_kind="absolute_maximum",
            maximum_bus_voltage_v=3.3,
            limit_basis="Synthetic datasheet",
        )
        with self.assertRaisesRegex(ValueError, "input pins must be unique"):
            I2cPullupVoltageCompatibilityRequirement(
                input_scope_basis="Synthetic reviewed endpoint inventory",
                maximum_rail_voltage_v=3.3,
                rail_basis="Synthetic rail range",
                input_limits=(limit, limit),
            )

    def test_i2c_series_pullup_contract_checks_exact_chain_and_branch_free_junctions(self) -> None:
        specification = i2c_series_pullup_requirement()
        observed = i2c_series_pullup_netlist()
        checks = {item.id: item for item in i2c_pullup_checks(specification, observed)}
        self.assertEqual(checks["i2c-pullup/series-bus/sda/series/sda-chain"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/series-bus/sda/series/sda-chain"].observed, 4_700)
        self.assertEqual(checks["i2c-pullup/series-bus/sda"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/series-bus/sda"].observed, 4_700)
        self.assertEqual(checks["i2c-pullup/series-bus/scl"].status, "PASS")

        parallel_requirement_data = specification.model_dump()
        parallel_requirement_data["buses"][0]["sda"]["minimum_ohms"] = 2_300
        parallel_requirement_data["buses"][0]["sda"]["maximum_ohms"] = 2_500
        parallel_requirement = I2cPullupAnalysis.model_validate(parallel_requirement_data)
        parallel_components = dict(observed.components)
        parallel_components["R13"] = ComponentContract(value="4.7k", footprint="Synthetic:R")
        parallel_symbols = dict(observed.component_symbols)
        parallel_symbols["R13"] = "Device:R"
        parallel_functions = dict(observed.pin_functions)
        parallel_functions.update({"R13.1": "1", "R13.2": "2"})
        parallel_pin_numbers = dict(observed.component_pin_numbers)
        parallel_pin_numbers["R13"] = ("1", "2")
        parallel_nets = dict(observed.nets)
        parallel_nets["I2C_SDA"] = (*parallel_nets["I2C_SDA"], "R13.1")
        parallel_nets["+3V3"] = (*parallel_nets["+3V3"], "R13.2")
        parallel_observed = observed.model_copy(
            update={
                "components": parallel_components,
                "component_symbols": parallel_symbols,
                "pin_functions": parallel_functions,
                "component_pin_numbers": parallel_pin_numbers,
                "nets": parallel_nets,
            }
        )
        parallel_checks = {
            item.id: item for item in i2c_pullup_checks(parallel_requirement, parallel_observed)
        }
        self.assertEqual(
            parallel_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status,
            "PASS",
        )
        self.assertEqual(parallel_checks["i2c-pullup/series-bus/sda"].status, "PASS")
        self.assertEqual(parallel_checks["i2c-pullup/series-bus/sda"].observed, 2_350)

        faults = (
            (i2c_series_pullup_netlist(first_value="2k"), "R10 is 2000Ω, outside 900–1100Ω"),
            (i2c_series_pullup_netlist(first_symbol="Device:C"), "R10 symbol is Device:C"),
            (
                i2c_series_pullup_netlist(second_footprint="Synthetic:WRONG"),
                "R11 footprint is Synthetic:WRONG",
            ),
            (i2c_series_pullup_netlist(dnp=("R10",)), "R10 is DNP"),
            (i2c_series_pullup_netlist(extra_junction_pin=True), "series junction I2C_SDA_CHAIN"),
        )
        for faulty_netlist, expected in faults:
            with self.subTest(expected=expected):
                failed = {
                    item.id: item for item in i2c_pullup_checks(specification, faulty_netlist)
                }
                self.assertEqual(
                    failed["i2c-pullup/series-bus/sda/series/sda-chain"].status, "FAIL"
                )
                self.assertIn(
                    expected,
                    failed["i2c-pullup/series-bus/sda/series/sda-chain"].detail,
                )
                self.assertEqual(failed["i2c-pullup/series-bus/sda"].status, "FAIL")

        missing_inventory = observed.model_copy(
            update={
                "component_pin_numbers": {
                    reference: numbers
                    for reference, numbers in observed.component_pin_numbers.items()
                    if reference != "R11"
                }
            }
        )
        inventory_checks = {
            item.id: item for item in i2c_pullup_checks(specification, missing_inventory)
        }
        self.assertEqual(
            inventory_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status, "FAIL"
        )
        self.assertIn(
            "R11 native pin inventory is missing",
            inventory_checks["i2c-pullup/series-bus/sda/series/sda-chain"].detail,
        )

    def test_i2c_series_pullup_contract_rejects_incomplete_or_unbound_paths(self) -> None:
        path = i2c_series_pullup_requirement().series_paths[0]
        path_data = path.model_dump()
        path_data["resistors"][1]["from_net"] = "WRONG_MIDPOINT"
        with self.assertRaisesRegex(ValueError, "ordered path"):
            I2cPullupSeriesPathRequirement.model_validate(path_data)

        requirement_data = i2c_series_pullup_requirement().model_dump()
        requirement_data["buses"][0]["sda"]["net"] = "ANOTHER_SDA"
        with self.assertRaisesRegex(ValueError, "match a configured signal/rail pair"):
            I2cPullupAnalysis.model_validate(requirement_data)

    def test_i2c_pullup_contract_excludes_dnp_and_unmapped_resistor_arrays(self) -> None:
        dnp = i2c_pullup_netlist(dnp=("R2",))
        checks = {item.id: item for item in i2c_pullup_checks(i2c_pullup_requirement(), dnp)}
        self.assertEqual(checks["i2c-pullup/control/sda"].status, "FAIL")
        self.assertEqual(checks["i2c-pullup/control/sda"].observed, 4_700)
        self.assertNotIn("R2", checks["i2c-pullup/control/sda"].detail)

        array = i2c_pullup_netlist(sda_values=("4.7k",), array_reference="R1")
        checks = {item.id: item for item in i2c_pullup_checks(i2c_pullup_requirement(), array)}
        self.assertEqual(checks["i2c-pullup/control/sda"].status, "FAIL")
        self.assertIsNone(checks["i2c-pullup/control/sda"].observed)

    def test_i2c_pullup_contract_accepts_only_explicit_complete_array_maps(self) -> None:
        specification = i2c_pullup_array_requirement()
        valid = i2c_pullup_array_netlist()
        checks = {item.id: item for item in i2c_pullup_checks(specification, valid)}
        self.assertEqual(checks["i2c-pullup/array-bus/sda"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/array-bus/scl"].status, "PASS")
        self.assertEqual(checks["i2c-pullup/array-bus/sda"].observed, 4_700)
        self.assertIn("RN1.sda=4700Ω", checks["i2c-pullup/array-bus/sda"].detail)

        extra_pin = i2c_pullup_array_netlist(extra_pin=True)
        incomplete = {item.id: item for item in i2c_pullup_checks(specification, extra_pin)}
        self.assertEqual(incomplete["i2c-pullup/array-bus/sda"].status, "FAIL")
        self.assertIn(
            "unreviewed symbol pins outside the array map",
            incomplete["i2c-pullup/array-bus/sda"].detail,
        )

        reviewed_unused_pin = i2c_pullup_array_requirement(
            unmapped_pin_reasons={"RN1.5": "Synthetic channel is not used by this board"}
        )
        covered_extra_pin = {
            item.id: item for item in i2c_pullup_checks(reviewed_unused_pin, extra_pin)
        }
        self.assertEqual(covered_extra_pin["i2c-pullup/array-bus/sda"].status, "PASS")

        faults = (
            (i2c_pullup_array_netlist(value="4x10k"), "value is 4x10k"),
            (
                i2c_pullup_array_netlist(symbol="Synthetic:OtherArray"),
                "symbol is Synthetic:OtherArray",
            ),
            (i2c_pullup_array_netlist(footprint="Synthetic:RA8"), "footprint is Synthetic:RA8"),
            (
                i2c_pullup_array_netlist(sda_signal_net="WRONG_SDA"),
                "expected one pin on I2C_SDA and one on +3V3",
            ),
            (i2c_pullup_array_netlist(dnp=("RN1",)), "RN1 is DNP"),
        )
        for observed, expected in faults:
            with self.subTest(expected=expected):
                failed = {item.id: item for item in i2c_pullup_checks(specification, observed)}
                self.assertEqual(failed["i2c-pullup/array-bus/sda"].status, "FAIL")
                self.assertIn(expected, failed["i2c-pullup/array-bus/sda"].detail)

    def test_i2c_pullup_requirement_rejects_ambiguous_signal_and_range_definitions(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct signal nets"):
            I2cPullupBusRequirement(
                id="same-line",
                basis="Synthetic invalid contract",
                sda=I2cPullupLineRequirement(
                    net="I2C", rail="+3V3", minimum_ohms=1_000, maximum_ohms=10_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C", rail="+3V3", minimum_ohms=1_000, maximum_ohms=10_000
                ),
            )
        with self.assertRaisesRegex(ValueError, "maximum resistance is below its minimum"):
            I2cPullupLineRequirement(
                net="I2C_SDA", rail="+3V3", minimum_ohms=10_000, maximum_ohms=1_000
            )
        conflicting_voltages = i2c_pullup_window_requirement().buses[0].sda.model_dump()
        assert conflicting_voltages["voltage_compatibility"] is not None
        conflicting_voltages["voltage_compatibility"]["maximum_rail_voltage_v"] = 3.45
        with self.assertRaisesRegex(ValueError, "rail ceilings must match"):
            I2cPullupLineRequirement.model_validate(conflicting_voltages)

    def test_spi_contract_checks_controller_membership_chip_selects_and_shared_selection(
        self,
    ) -> None:
        spec = spi_requirement()
        checks = {item.id: item for item in spi_checks(spec, spi_netlist(spec))}
        self.assertTrue(checks)
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        self.assertEqual(checks["spi/control/device/sensor/route/sck"].status, "PASS")
        self.assertEqual(checks["spi/control/device/memory/route/miso"].status, "PASS")

        disconnected = {
            item.id: item
            for item in spi_checks(spec, spi_netlist(spec, fault="device2-cs-disconnected"))
        }
        self.assertEqual(disconnected["spi/control/device/memory/pins"].status, "FAIL")
        self.assertIn("expected SPI_CS1", disconnected["spi/control/device/memory/pins"].detail)

        wrong_net = {
            item.id: item
            for item in spi_checks(spec, spi_netlist(spec, fault="device2-cs-wrong-net"))
        }
        self.assertEqual(wrong_net["spi/control/device/memory/pins"].status, "FAIL")
        self.assertIn("UNEXPECTED_CS", wrong_net["spi/control/device/memory/pins"].detail)

        shared = spi_requirement(shared_select=True)
        shared_checks = {item.id: item for item in spi_checks(shared, spi_netlist(shared))}
        self.assertTrue(
            all(item.status in {"PASS", "NOT_APPLICABLE"} for item in shared_checks.values())
        )
        invalid_devices = (
            shared.buses[0].devices[0],
            SpiDeviceRequirement.model_validate(
                {
                    **shared.buses[0].devices[1].model_dump(),
                    "shared_select_group": None,
                }
            ),
        )
        with self.assertRaisesRegex(ValueError, "shared without one explicit"):
            SpiBusRequirement(
                id="control",
                basis=shared.buses[0].basis,
                controller=shared.buses[0].controller,
                devices=invalid_devices,
            )

    def test_spi_contract_allows_write_only_devices_and_checks_buffered_miso_endpoints(
        self,
    ) -> None:
        for disposition in ("unconnected", "not_present"):
            with self.subTest(disposition=disposition):
                spec = spi_requirement(device2_miso=disposition)
                checks = {item.id: item for item in spi_checks(spec, spi_netlist(spec))}
                self.assertEqual(
                    checks["spi/control/device/memory/route/miso"].status,
                    "NOT_APPLICABLE",
                )
                self.assertTrue(
                    all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
                )

        buffered = spi_requirement(buffered_miso=True, device2_miso="not_present")
        checks = {item.id: item for item in spi_checks(buffered, spi_netlist(buffered))}
        self.assertEqual(checks["spi/control/bridge/U9/pins"].status, "PASS")
        self.assertEqual(checks["spi/control/device/sensor/route/miso"].status, "PASS")
        self.assertIn(
            "Internal bridge behavior is not verified",
            checks["spi/control/device/sensor/route/miso"].detail,
        )

        wrong_bridge = {
            item.id: item
            for item in spi_checks(buffered, spi_netlist(buffered, fault="bridge-output-wrong-net"))
        }
        self.assertEqual(wrong_bridge["spi/control/bridge/U9/pins"].status, "FAIL")
        self.assertEqual(wrong_bridge["spi/control/device/sensor/route/miso"].status, "FAIL")

    def test_spi_contract_rejects_missing_controller_mapping_and_unapproved_shared_cs(self) -> None:
        spec = spi_requirement()
        bus = spec.buses[0]
        with self.assertRaisesRegex(ValueError, "has no declared controller pin"):
            SpiBusRequirement(
                id="control",
                basis=bus.basis,
                controller=bus.controller.model_copy(
                    update={"chip_selects": bus.controller.chip_selects[:1]}
                ),
                devices=bus.devices,
            )

    def test_serial_peer_map_checks_crossed_tx_rx_and_authored_reference_policy(self) -> None:
        direct = serial_peer_requirement()
        checks = {item.id: item for item in serial_peer_checks(direct, serial_peer_netlist(direct))}
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        self.assertEqual(checks["serial/console-link/route/a_tx_to_b_rx"].status, "PASS")
        self.assertEqual(checks["serial/console-link/route/b_tx_to_a_rx"].status, "PASS")
        self.assertEqual(checks["serial/console-link/reference"].status, "PASS")
        self.assertEqual(checks["serial/console-link/logic-voltage/a_tx_to_b_rx"].status, "PASS")
        self.assertEqual(checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status, "PASS")

        exact_absolute_limit = serial_peer_requirement(peer_output_high_maximum_v=3.6)
        exact_limit_checks = {
            item.id: item
            for item in serial_peer_checks(
                exact_absolute_limit, serial_peer_netlist(exact_absolute_limit)
            )
        }
        self.assertEqual(
            exact_limit_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status,
            "PASS",
        )
        self.assertEqual(
            exact_limit_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].observed,
            0.0,
        )

        overvoltage = serial_peer_requirement(peer_output_high_maximum_v=5.0)
        overvoltage_checks = {
            item.id: item
            for item in serial_peer_checks(overvoltage, serial_peer_netlist(overvoltage))
        }
        unsafe_high = overvoltage_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"]
        self.assertEqual(unsafe_high.status, "FAIL")
        self.assertAlmostEqual(unsafe_high.observed or 0.0, -1.4)
        self.assertIn("Synthetic UART datasheet Rev A", unsafe_high.detail)

        weak_low = serial_peer_requirement(peer_output_low_maximum_v=0.9)
        weak_low_checks = {
            item.id: item for item in serial_peer_checks(weak_low, serial_peer_netlist(weak_low))
        }
        self.assertEqual(
            weak_low_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status,
            "FAIL",
        )

        limits_missing = serial_peer_requirement(include_logic_limits=False)
        missing_checks = {
            item.id: item
            for item in serial_peer_checks(limits_missing, serial_peer_netlist(limits_missing))
        }
        self.assertEqual(
            missing_checks["serial/console-link/logic-voltage/a_tx_to_b_rx"].status,
            "NOT_CONFIGURED",
        )

        with self.assertRaisesRegex(ValueError, "ordered and non-overlapping"):
            SerialLogicOutputLimits(
                low_minimum_v=0.0,
                low_maximum_v=2.1,
                high_minimum_v=2.0,
                high_maximum_v=3.3,
                source="Synthetic invalid datasheet range",
                conditions="Synthetic operating range",
            )
        with self.assertRaisesRegex(ValueError, "absolute limits and logic thresholds"):
            SerialLogicInputLimits(
                absolute_minimum_v=-0.3,
                low_maximum_v=2.1,
                high_minimum_v=2.0,
                absolute_maximum_v=3.6,
                source="Synthetic invalid datasheet range",
                conditions="Synthetic operating range",
            )

        crossed_wrongly = {
            item.id: item
            for item in serial_peer_checks(direct, serial_peer_netlist(direct, fault="tx-to-tx"))
        }
        self.assertEqual(crossed_wrongly["serial/console-link/endpoint/device/pins"].status, "FAIL")
        self.assertEqual(crossed_wrongly["serial/console-link/route/a_tx_to_b_rx"].status, "FAIL")

        separate = serial_peer_requirement(reference_policy="separate_nets")
        separate_checks = {
            item.id: item for item in serial_peer_checks(separate, serial_peer_netlist(separate))
        }
        self.assertEqual(separate_checks["serial/console-link/reference"].status, "PASS")

        no_reference = serial_peer_requirement(reference_policy="not_applicable")
        no_reference_checks = {
            item.id: item
            for item in serial_peer_checks(no_reference, serial_peer_netlist(no_reference))
        }
        self.assertEqual(
            no_reference_checks["serial/console-link/reference"].status, "NOT_APPLICABLE"
        )

        missing_return = {
            item.id: item
            for item in serial_peer_checks(
                direct, serial_peer_netlist(direct, fault="remote-reference-unconnected")
            )
        }
        self.assertEqual(missing_return["serial/console-link/reference"].status, "FAIL")

        wrong_local_reference = {
            item.id: item
            for item in serial_peer_checks(
                direct, serial_peer_netlist(direct, fault="local-reference-wrong-net")
            )
        }
        self.assertEqual(wrong_local_reference["serial/console-link/reference"].status, "FAIL")

        with self.assertRaisesRegex(ValueError, "same logic voltage domain"):
            serial_peer_requirement(peer_logic_domain="logic-5v")
        with self.assertRaisesRegex(ValueError, "different logic voltage domains"):
            serial_peer_requirement(peer_mode="level_shifted")

    def test_serial_peer_bonded_reference_policy_checks_exact_fitted_component(self) -> None:
        spec = serial_peer_requirement(reference_policy="bonded")
        control = {item.id: item for item in serial_peer_checks(spec, serial_peer_netlist(spec))}
        self.assertEqual(control["serial/console-link/reference"].status, "PASS")

        fault_details = {
            "bond-missing": "R3 is absent or ambiguous",
            "bond-wrong-value": "R3 value is 1R; expected 0R",
            "bond-wrong-footprint": "R3 footprint is Synthetic:0402; expected Synthetic:0603",
            "bond-wrong-symbol": "R3 symbol is Device:C; expected Device:R",
            "bond-dnp": "R3 is marked DNP",
            "bond-active-pin": "R3.2 is not exported as a passive bond pin",
            "bond-wrong-net": "R3.2 is on FLOATING_GND; expected GND_B",
            "remote-reference-unconnected": "U11.3 is assigned to unconnected; expected GND_B",
        }
        for fault, expected_detail in fault_details.items():
            with self.subTest(fault=fault):
                checks = {
                    item.id: item
                    for item in serial_peer_checks(spec, serial_peer_netlist(spec, fault=fault))
                }
                reference_check = checks["serial/console-link/reference"]
                self.assertEqual(reference_check.status, "FAIL")
                self.assertIn(expected_detail, reference_check.detail)

        observed = serial_peer_netlist(spec)
        reordered = observed.model_copy(
            update={
                "components": dict(reversed(tuple(observed.components.items()))),
                "nets": {
                    net: tuple(reversed(pins))
                    for net, pins in reversed(tuple(observed.nets.items()))
                },
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "component_pin_numbers": {
                    reference: tuple(reversed(numbers))
                    for reference, numbers in reversed(
                        tuple(observed.component_pin_numbers.items())
                    )
                },
                "pin_electrical_types": dict(
                    reversed(tuple(observed.pin_electrical_types.items()))
                ),
            }
        )
        self.assertEqual(serial_peer_checks(spec, observed), serial_peer_checks(spec, reordered))

    def test_serial_peer_bond_policy_requires_distinct_mapped_nets_and_component(self) -> None:
        spec = serial_peer_requirement(reference_policy="bonded")
        link = spec.links[0]
        values = link.model_dump(mode="python")
        values["reference_bond"] = None
        with self.assertRaisesRegex(ValueError, "needs one exact bond component"):
            SerialPeerLinkRequirement.model_validate(values)

        values = link.model_dump(mode="python")
        values["reference_bond"] = link.reference_bond.model_copy(
            update={"side_b_net": "FLOATING_GND"}
        )
        with self.assertRaisesRegex(ValueError, "must join the two mapped endpoint nets"):
            SerialPeerLinkRequirement.model_validate(values)

        values = serial_peer_requirement().links[0].model_dump(mode="python")
        values["reference_bond"] = link.reference_bond
        values["reference_policy"] = "common_net"
        with self.assertRaisesRegex(ValueError, "cannot declare a bond"):
            SerialPeerLinkRequirement.model_validate(values)

    def test_serial_peer_map_supports_level_shifted_and_external_unknown_peers(self) -> None:
        shifted = serial_peer_requirement(peer_mode="level_shifted", peer_logic_domain="logic-5v")
        shifted_checks = {
            item.id: item for item in serial_peer_checks(shifted, serial_peer_netlist(shifted))
        }
        self.assertTrue(
            all(item.status in {"PASS", "NOT_APPLICABLE"} for item in shifted_checks.values())
        )
        self.assertEqual(shifted_checks["serial/console-link/bridge/U9/pins"].status, "PASS")
        self.assertEqual(shifted_checks["serial/console-link/voltage-domain"].status, "PASS")
        self.assertEqual(
            shifted_checks["serial/console-link/logic-voltage"].status, "NOT_APPLICABLE"
        )

        wrong_bridge = {
            item.id: item
            for item in serial_peer_checks(
                shifted, serial_peer_netlist(shifted, fault="bridge-output-wrong-net")
            )
        }
        self.assertEqual(wrong_bridge["serial/console-link/bridge/U9/pins"].status, "FAIL")
        self.assertEqual(wrong_bridge["serial/console-link/route/a_tx_to_b_rx"].status, "FAIL")
        self.assertEqual(wrong_bridge["serial/console-link/voltage-domain"].status, "FAIL")

        external = serial_peer_requirement(peer_mode="external")
        external_checks = {
            item.id: item for item in serial_peer_checks(external, serial_peer_netlist(external))
        }
        self.assertEqual(
            external_checks["serial/console-link/endpoint/console/pins"].status, "PASS"
        )
        self.assertEqual(external_checks["serial/console-link/peer-map"].status, "NOT_APPLICABLE")
        self.assertEqual(
            external_checks["serial/console-link/voltage-domain"].status, "NOT_APPLICABLE"
        )
        self.assertEqual(
            external_checks["serial/console-link/logic-voltage"].status, "NOT_APPLICABLE"
        )
        self.assertEqual(external_checks["serial/console-link/reference"].status, "NOT_APPLICABLE")

        shared = spi_requirement(shared_select=True)
        bus = shared.buses[0]
        with self.assertRaisesRegex(ValueError, "Every declared SPI controller chip-select"):
            SpiBusRequirement(
                id=bus.id,
                basis=bus.basis,
                controller=bus.controller.model_copy(
                    update={
                        "chip_selects": (
                            *bus.controller.chip_selects,
                            SpiPinNetRequirement(pin="U1.5", net="SPI_CS1"),
                        )
                    }
                ),
                devices=bus.devices,
            )

    def test_rs485_contract_checks_authored_pair_termination_bias_and_faults(self) -> None:
        spec = rs485_requirement()
        checks = {item.id: item for item in rs485_checks(spec, rs485_netlist(spec))}
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        self.assertEqual(checks["rs485/fieldbus/endpoint/controller/identity"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/endpoint/bus-connector/pins"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/membership"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/termination/local-end"].observed, 120)
        self.assertEqual(checks["rs485/fieldbus/pair/shared/bias"].status, "PASS")

        fault_expectations = {
            "endpoint-line-wrong-net": (
                "rs485/fieldbus/endpoint/controller/pins",
                "FAIL",
            ),
            "endpoint-reference-wrong-net": (
                "rs485/fieldbus/endpoint/bus-connector/pins",
                "FAIL",
            ),
            "termination-dnp": (
                "rs485/fieldbus/pair/shared/termination/local-end",
                "FAIL",
            ),
            "termination-wrong-net": (
                "rs485/fieldbus/pair/shared/termination/local-end",
                "FAIL",
            ),
            "bias-dnp": ("rs485/fieldbus/pair/shared/bias", "FAIL"),
            "bias-wrong-net": ("rs485/fieldbus/pair/shared/bias", "FAIL"),
            "identity-wrong": ("rs485/fieldbus/endpoint/controller/identity", "FAIL"),
        }
        for fault, (check_id, status) in fault_expectations.items():
            with self.subTest(fault=fault):
                rows = {
                    item.id: item for item in rs485_checks(spec, rs485_netlist(spec, fault=fault))
                }
                self.assertEqual(rows[check_id].status, status)

        split = rs485_requirement(termination_mode="split")
        split_checks = {item.id: item for item in rs485_checks(split, rs485_netlist(split))}
        self.assertEqual(
            split_checks["rs485/fieldbus/pair/shared/termination/local-end"].status, "PASS"
        )
        self.assertEqual(
            split_checks["rs485/fieldbus/pair/shared/termination/local-end"].observed, 120
        )

        optional = rs485_requirement(dnp_option=True)
        optional_checks = {
            item.id: item for item in rs485_checks(optional, rs485_netlist(optional))
        }
        self.assertEqual(
            optional_checks["rs485/fieldbus/pair/shared/termination/remote-end/dnp-options"].status,
            "PASS",
        )
        fitted_option = {
            item.id: item
            for item in rs485_checks(optional, rs485_netlist(optional, fault="dnp-option-fitted"))
        }
        self.assertEqual(
            fitted_option["rs485/fieldbus/pair/shared/termination/remote-end/dnp-options"].status,
            "FAIL",
        )

    def test_rs485_contract_records_duplex_isolation_and_bias_applicability(self) -> None:
        full_duplex = rs485_requirement(
            topology="four_wire_full_duplex",
            termination_mode="split",
            bias_mode="internal_failsafe",
            isolated=True,
            external_peers=("Remote controller pin map not supplied",),
        )
        checks = {item.id: item for item in rs485_checks(full_duplex, rs485_netlist(full_duplex))}
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        for pair_id in ("board-to-peer", "peer-to-board"):
            self.assertEqual(checks[f"rs485/fieldbus/pair/{pair_id}/membership"].status, "PASS")
            self.assertEqual(
                checks[f"rs485/fieldbus/pair/{pair_id}/termination/local-end"].status,
                "PASS",
            )
            internal = checks[f"rs485/fieldbus/pair/{pair_id}/bias"]
            self.assertEqual(internal.status, "NOT_APPLICABLE")
            self.assertIn("not verified from the netlist", internal.detail)
        self.assertEqual(checks["rs485/fieldbus/endpoint/controller/pins"].status, "PASS")
        self.assertTrue(
            any(
                item.status == "NOT_APPLICABLE"
                and "remote controller pin map not supplied" in item.detail.casefold()
                for item in checks.values()
            )
        )

        for bias_mode in ("remote", "not_required"):
            with self.subTest(bias_mode=bias_mode):
                declared = rs485_requirement(bias_mode=bias_mode)
                rows = {item.id: item for item in rs485_checks(declared, rs485_netlist(declared))}
                self.assertEqual(rows["rs485/fieldbus/pair/shared/bias"].status, "NOT_APPLICABLE")

        bus = rs485_requirement().buses[0]
        with self.assertRaisesRegex(ValueError, "Four-wire RS-485 needs"):
            Rs485BusRequirement(
                id=bus.id,
                basis=bus.basis,
                topology="four_wire_full_duplex",
                pairs=bus.pairs,
                endpoints=bus.endpoints,
            )

    def test_power_connectivity_checks_authored_sources_loads_and_alternatives(self) -> None:
        spec = power_connectivity_requirement()
        checks = {
            item.id: item for item in power_connectivity_checks(spec, power_connectivity_netlist())
        }
        self.assertTrue(all(item.status == "PASS" for item in checks.values()))
        self.assertEqual(
            checks["power-connectivity/supply/source/approved-inputs"].status,
            "PASS",
        )
        self.assertEqual(
            checks["power-connectivity/supply/load/load"].status,
            "PASS",
        )
        fault_expectations = {
            "source-wrong-net": "power-connectivity/supply/source/approved-inputs",
            "load-wrong-net": "power-connectivity/supply/load/load",
            "source-dnp": "power-connectivity/supply/source/approved-inputs",
            "source-identity-wrong": "power-connectivity/supply/source/approved-inputs",
        }
        for fault, check_id in fault_expectations.items():
            with self.subTest(fault=fault):
                rows = {
                    item.id: item
                    for item in power_connectivity_checks(
                        spec, power_connectivity_netlist(fault=fault)
                    )
                }
                self.assertEqual(rows[check_id].status, "FAIL")

        alternatives = power_connectivity_requirement(source_selection="any")
        one_available = {
            item.id: item
            for item in power_connectivity_checks(
                alternatives, power_connectivity_netlist(fault="source-dnp")
            )
        }
        self.assertEqual(
            one_available["power-connectivity/supply/source/approved-inputs"].status,
            "PASS",
        )
        none_available = {
            item.id: item
            for item in power_connectivity_checks(
                alternatives, power_connectivity_netlist(fault="all-sources-dnp")
            )
        }
        self.assertEqual(
            none_available["power-connectivity/supply/source/approved-inputs"].status,
            "FAIL",
        )

    def test_power_connectivity_map_covers_power_budget_rail_and_load_ids(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        source_rail = power_connectivity_requirement().rails[0]
        mapped = PowerConnectivityAnalysis(
            basis="Synthetic connectivity map matched to its budget",
            rails=(
                PowerConnectivityRailRequirement(
                    id="supply",
                    basis="Existing budget rail with exact schematic membership",
                    net="VIN_IN",
                    source_groups=source_rail.source_groups,
                    loads=(
                        PowerLoadConnectivityRequirement(
                            id="load",
                            basis="Existing budget load covers both selected components",
                            endpoints=tuple(
                                endpoint
                                for load in source_rail.loads
                                for endpoint in load.endpoints
                            ),
                        ),
                    ),
                ),
            ),
        )
        raw = json.loads(contract.model_dump_json())
        raw["power_connectivity"] = json.loads(mapped.model_dump_json())
        validated = ElectricalAnalysisContract.model_validate_json(json.dumps(raw))
        self.assertIsNotNone(validated.power_connectivity)

        raw["power_connectivity"]["rails"][0]["loads"][0]["id"] = "unbudgeted-load"
        with self.assertRaisesRegex(ValueError, "load IDs must match"):
            ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_usb_c_source_contract_checks_role_cc_values_vbus_ground_and_protection(self) -> None:
        baseline = usb_c_netlist()
        checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), baseline)}
        self.assertTrue(checks)
        self.assertTrue(all(item.status == "PASS" for item in checks.values()))
        self.assertEqual(checks["usb-c/host-port/cc1-attachment"].observed, 56_000)

        extra_pullup = baseline.model_copy(
            update={
                "components": {
                    **baseline.components,
                    "R3": ComponentContract(value="56k", footprint="Synthetic:R_0603"),
                },
                "component_symbols": {**baseline.component_symbols, "R3": "Device:R"},
                "component_pin_numbers": {
                    **baseline.component_pin_numbers,
                    "R3": ("1", "2"),
                },
                "pin_functions": {
                    **baseline.pin_functions,
                    "R3.1": "1",
                    "R3.2": "2",
                },
                "nets": {
                    **baseline.nets,
                    "CC1": (*baseline.nets["CC1"], "R3.1"),
                    "+5V": (*baseline.nets["+5V"], "R3.2"),
                },
            }
        )
        extra_checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), extra_pullup)}
        self.assertEqual(extra_checks["usb-c/host-port/cc1-attachment"].status, "FAIL")
        self.assertIn(
            "unlisted fitted resistors", extra_checks["usb-c/host-port/cc1-attachment"].detail
        )

        wrong_cc = baseline.model_copy(
            update={
                "nets": {
                    **{
                        name: tuple(pin for pin in pins if pin != "J1.5")
                        for name, pins in baseline.nets.items()
                    },
                    "WRONG_CC": ("J1.5",),
                }
            }
        )
        wrong_cc_checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_cc)}
        self.assertEqual(wrong_cc_checks["usb-c/host-port/connector-pins"].status, "FAIL")

        dnp_checks = {
            item.id: item for item in usb_c_checks(usb_c_requirement(), usb_c_netlist(dnp=("R2",)))
        }
        self.assertEqual(dnp_checks["usb-c/host-port/cc2-attachment"].status, "FAIL")
        self.assertIn("DNP", dnp_checks["usb-c/host-port/cc2-attachment"].detail)

        wrong_vbus = baseline.model_copy(
            update={
                "nets": {
                    **{
                        name: pins
                        for name, pins in baseline.nets.items()
                        if name not in {"VBUS_PORT"}
                    },
                    "VBUS_PORT": (),
                    "VBUS_WRONG": ("J1.1",),
                }
            }
        )
        vbus_checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_vbus)}
        self.assertEqual(vbus_checks["usb-c/host-port/connector-pins"].status, "FAIL")
        self.assertIn("J1.1", vbus_checks["usb-c/host-port/connector-pins"].detail)

        wrong_protection = baseline.model_copy(
            update={
                "nets": {
                    **{
                        name: tuple(pin for pin in pins if pin != "D1.2")
                        for name, pins in baseline.nets.items()
                    },
                    "WRONG_PROTECTION_RETURN": ("D1.2",),
                }
            }
        )
        protection_checks = {
            item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_protection)
        }
        self.assertEqual(protection_checks["usb-c/host-port/protection/D1"].status, "FAIL")

        wrong_footprint = {
            item.id: item
            for item in usb_c_checks(
                usb_c_requirement(), usb_c_netlist(footprint="Package_DFN:Wrong")
            )
        }
        self.assertEqual(wrong_footprint["usb-c/host-port/protection/D1"].status, "FAIL")

    def test_usb_c_dual_role_checks_exact_controller_and_marks_debug_accessory_unsupported(
        self,
    ) -> None:
        spec = usb_c_requirement(role="dual_role", controller=True)
        observed = usb_c_netlist(controller=True)
        checks = {item.id: item for item in usb_c_checks(spec, observed)}
        self.assertTrue(all(item.status == "PASS" for item in checks.values()))
        self.assertEqual(checks["usb-c/host-port/controller-identity"].status, "PASS")

        wrong_controller_pin = observed.model_copy(
            update={
                "nets": {
                    **{
                        name: tuple(pin for pin in pins if pin != "U2.6")
                        for name, pins in observed.nets.items()
                    },
                    "CC1": (*observed.nets["CC1"], "U2.6"),
                }
            }
        )
        failed = {item.id: item for item in usb_c_checks(spec, wrong_controller_pin)}
        self.assertEqual(failed["usb-c/host-port/cc2-attachment"].status, "FAIL")

        wrong_controller_symbol = observed.model_copy(
            update={
                "component_symbols": {
                    **observed.component_symbols,
                    "U2": "Synthetic:OtherController",
                }
            }
        )
        identity_checks = {item.id: item for item in usb_c_checks(spec, wrong_controller_symbol)}
        self.assertEqual(identity_checks["usb-c/host-port/controller-identity"].status, "FAIL")

        debug_checks = {
            item.id: item
            for item in usb_c_checks(usb_c_requirement(role="debug_accessory"), usb_c_netlist())
        }
        self.assertEqual(debug_checks["usb-c/host-port/role-support"].status, "NOT_RUN")
        self.assertIn("not modeled", debug_checks["usb-c/host-port/role-support"].detail)

    def test_usb_c_static_mode_strap_uses_generic_pin_connectivity_contract(self) -> None:
        observed = usb_c_netlist(role="dual_role", controller=True)
        grounded_mode_pin = observed.model_copy(
            update={
                "nets": {
                    **observed.nets,
                    "GND": (*observed.nets["GND"], "U2.7"),
                }
            }
        )
        mode_requirement = PinConnectivityAnalysis(
            basis="Synthetic controller datasheet review for a static mode strap",
            rules=(
                PinRelationshipRule(
                    id="controller-mode-strap",
                    basis="This synthetic controller uses a ground strap for the approved mode",
                    topology="common_net",
                    pins=("J1.2", "U2.7"),
                    net="GND",
                ),
            ),
        )
        self.assertEqual(
            pin_relationship_checks(mode_requirement, grounded_mode_pin)[0].status, "PASS"
        )

        wrong_mode = grounded_mode_pin.model_copy(
            update={
                "nets": {
                    **{
                        net: tuple(pin for pin in pins if pin != "U2.7")
                        for net, pins in grounded_mode_pin.nets.items()
                    },
                    "+5V": (*grounded_mode_pin.nets.get("+5V", ()), "U2.7"),
                }
            }
        )
        failed = pin_relationship_checks(mode_requirement, wrong_mode)[0]
        self.assertEqual(failed.status, "FAIL")
        self.assertIn("U2.7", failed.detail)

    def test_usb_c_sink_checks_rd_to_ground(self) -> None:
        spec = usb_c_requirement(role="sink")
        observed = usb_c_netlist(role="sink")
        checks = {item.id: item for item in usb_c_checks(spec, observed)}
        self.assertTrue(all(item.status == "PASS" for item in checks.values()))
        self.assertEqual(checks["usb-c/host-port/cc1-attachment"].observed, 5_100)

        miswired = observed.model_copy(
            update={
                "nets": {
                    **{
                        name: tuple(pin for pin in pins if pin != "R1.2")
                        for name, pins in observed.nets.items()
                    },
                    "+5V": ("R1.2",),
                }
            }
        )
        miswired_checks = {item.id: item for item in usb_c_checks(spec, miswired)}
        self.assertEqual(miswired_checks["usb-c/host-port/cc1-attachment"].status, "FAIL")

    def test_usb_c_vbus_path_is_opt_in_and_checks_authored_component_pin_chain(self) -> None:
        base_spec = usb_c_requirement()
        base_checks = {item.id: item for item in usb_c_checks(base_spec, usb_c_netlist())}
        self.assertFalse(any("/vbus-path/" in check_id for check_id in base_checks))

        spec = usb_c_requirement(vbus_path=True)
        observed = usb_c_netlist(vbus_path=True)
        check_id = "usb-c/host-port/vbus-path/input-path"
        passing = {item.id: item for item in usb_c_checks(spec, observed)}
        self.assertEqual(passing[check_id].status, "PASS")
        self.assertIn("native symbol, footprint, pin inventory", passing[check_id].detail)

        faults: tuple[tuple[str, NetlistContract, str], ...] = (
            (
                "mapped pin disconnected",
                observed.model_copy(
                    update={
                        "nets": {
                            **{
                                net: tuple(pin for pin in pins if pin != "U3.3")
                                for net, pins in observed.nets.items()
                            },
                        }
                    }
                ),
                "U3.3",
            ),
            (
                "wrong symbol",
                observed.model_copy(
                    update={
                        "component_symbols": {
                            **observed.component_symbols,
                            "F1": "Device:DifferentPart",
                        }
                    }
                ),
                "expected Device:Fuse",
            ),
            (
                "wrong footprint",
                observed.model_copy(
                    update={
                        "components": {
                            **observed.components,
                            "U3": ComponentContract(
                                value="Synthetic load switch", footprint="Package_DFN:Wrong"
                            ),
                        }
                    }
                ),
                "expected Package_DFN:DFN-6",
            ),
            ("unfitted fuse", usb_c_netlist(vbus_path=True, dnp=("F1",)), "DNP"),
            (
                "missing pin inventory",
                observed.model_copy(
                    update={
                        "component_pin_numbers": {
                            **{
                                reference: numbers
                                for reference, numbers in observed.component_pin_numbers.items()
                                if reference != "F1"
                            },
                        }
                    }
                ),
                "F1 native pin inventory is missing",
            ),
            (
                "missing component",
                observed.model_copy(
                    update={
                        "components": {
                            reference: component
                            for reference, component in observed.components.items()
                            if reference != "F1"
                        }
                    }
                ),
                "F1 is absent",
            ),
        )
        for label, fault, expected in faults:
            with self.subTest(fault=label):
                checks = {item.id: item for item in usb_c_checks(spec, fault)}
                self.assertEqual(checks[check_id].status, "FAIL")
                self.assertIn(expected, checks[check_id].detail)

    def test_usb_c_vbus_path_contract_rejects_discontinuous_or_unmapped_chains(self) -> None:
        raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
        path = raw["ports"][0]["vbus_path"]
        path["elements"][1]["port_side_net"] = "VBUS_WRONG"
        path["elements"][1]["pin_assignments"] = tuple(
            {
                **assignment,
                "net": "VBUS_WRONG",
            }
            if assignment["pin"] in {"U3.1", "U3.2"}
            else assignment
            for assignment in path["elements"][1]["pin_assignments"]
        )
        with self.assertRaisesRegex(ValueError, "ordered net chain"):
            UsbCAnalysis.model_validate(raw)

        raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
        path = raw["ports"][0]["vbus_path"]
        path["elements"][0]["pin_assignments"][0]["net"] = "VBUS_WRONG"
        with self.assertRaisesRegex(ValueError, "port-side pins must map"):
            UsbCAnalysis.model_validate(raw)

        raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
        raw["ports"][0]["vbus_path"]["board_net"] = "VBUS_WRONG"
        with self.assertRaisesRegex(ValueError, "end on the declared board-side net"):
            UsbCAnalysis.model_validate(raw)

    def test_can_contract_checks_both_declared_direct_endpoints_and_detects_extra_parts(
        self,
    ) -> None:
        checks = {
            item.id: item
            for item in can_termination_checks(
                can_termination_requirement(), can_termination_netlist()
            )
        }
        self.assertEqual(checks["can-termination/fieldbus/local-a"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local-b"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/unlisted-direct"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/signal-pins"].status, "PASS")

        misassigned_pins = can_termination_netlist().model_copy(
            update={
                "nets": {
                    "CAN_H": ("R1.1", "R2.1"),
                    "CAN_L": ("U1.2", "R1.2", "R2.2"),
                    "OTHER": ("U1.1",),
                }
            }
        )
        pin_check = {
            item.id: item
            for item in can_termination_checks(can_termination_requirement(), misassigned_pins)
        }["can-termination/fieldbus/signal-pins"]
        self.assertEqual(pin_check.status, "FAIL")
        self.assertIn("U1.1 is assigned to OTHER", pin_check.detail)

        stale_pin_check = {
            item.id: item
            for item in can_termination_checks(
                can_termination_requirement(high_pin="U9.7"), can_termination_netlist()
            )
        }["can-termination/fieldbus/signal-pins"]
        self.assertEqual(stale_pin_check.status, "FAIL")
        self.assertIn("U9.7 is absent", stale_pin_check.detail)

        boundary = can_termination_netlist(
            {"R1": ("108R", "CAN_H", "CAN_L"), "R2": ("132R", "CAN_H", "CAN_L")}
        )
        boundary_checks = {
            item.id: item
            for item in can_termination_checks(can_termination_requirement(), boundary)
        }
        self.assertEqual(boundary_checks["can-termination/fieldbus/local-a"].status, "PASS")
        self.assertEqual(boundary_checks["can-termination/fieldbus/local-b"].status, "PASS")

        no_termination = can_termination_netlist(paths={})
        no_termination_checks = {
            item.id
            for item in can_termination_checks(can_termination_requirement(), no_termination)
            if item.status == "FAIL"
        }
        self.assertIn("can-termination/fieldbus/local-a", no_termination_checks)
        self.assertIn("can-termination/fieldbus/local-b", no_termination_checks)

        missing = can_termination_netlist(paths={"R1": ("120R", "CAN_H", "CAN_L")})
        missing_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), missing)
        }
        self.assertEqual(missing_checks["can-termination/fieldbus/local-b"].status, "FAIL")
        self.assertIn("R2 is absent", missing_checks["can-termination/fieldbus/local-b"].detail)

        dnp = can_termination_netlist(dnp=("R1",))
        dnp_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), dnp)
        }
        self.assertEqual(dnp_checks["can-termination/fieldbus/local-a"].status, "FAIL")
        self.assertIn("R1 is DNP", dnp_checks["can-termination/fieldbus/local-a"].detail)

        low_value = can_termination_netlist(
            {"R1": ("100R", "CAN_H", "CAN_L"), "R2": ("120R", "CAN_H", "CAN_L")}
        )
        value_checks = {
            item.id
            for item in can_termination_checks(can_termination_requirement(), low_value)
            if item.status == "FAIL"
        }
        self.assertIn("can-termination/fieldbus/local-a", value_checks)

        extra = can_termination_netlist(
            {
                "R1": ("120R", "CAN_H", "CAN_L"),
                "R2": ("120R", "CAN_H", "CAN_L"),
                "R3": ("60R", "CAN_H", "CAN_L"),
            }
        )
        extra_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), extra)
        }
        self.assertEqual(extra_checks["can-termination/fieldbus/unlisted-direct"].status, "FAIL")
        self.assertIn("R3=60Ω", extra_checks["can-termination/fieldbus/unlisted-direct"].detail)

    def test_can_contract_checks_split_network_and_external_dnp_option(self) -> None:
        split = CanTerminationAnalysis(
            basis="Synthetic split termination requirement",
            buses=(
                CanTerminationBusRequirement(
                    id="fieldbus",
                    basis="Synthetic test bus",
                    high_net="CAN_H",
                    low_net="CAN_L",
                    high_pins=("U1.1",),
                    low_pins=("U1.2",),
                    endpoints=(
                        CanTerminationEndpointRequirement(
                            id="local",
                            basis="Two equal legs meet at the declared midpoint",
                            topology="split",
                            midpoint_net="CAN_TERM_MID",
                            resistors=(
                                CanTerminationResistorRequirement(
                                    reference="R4",
                                    first_net="CAN_H",
                                    second_net="CAN_TERM_MID",
                                    minimum_ohms=54,
                                    maximum_ohms=66,
                                ),
                                CanTerminationResistorRequirement(
                                    reference="R5",
                                    first_net="CAN_L",
                                    second_net="CAN_TERM_MID",
                                    minimum_ohms=54,
                                    maximum_ohms=66,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        split_paths = {
            "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
            "R5": ("60R", "CAN_L", "CAN_TERM_MID"),
        }
        checks = {
            item.id: item
            for item in can_termination_checks(split, can_termination_netlist(split_paths))
        }
        self.assertEqual(checks["can-termination/fieldbus/local"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local"].observed, 120)
        self.assertNotIn("can-termination/fieldbus/local/midpoint-capacitor", checks)

        midpoint_capacitor = CanTerminationMidpointCapacitorRequirement(
            reference="C1",
            expected_symbol="Device:C",
            expected_footprint="Synthetic:CAP",
            midpoint_pin="C1.1",
            reference_pin="C1.2",
            reference_net="GND",
            minimum_nominal_capacitance_pf=90,
            maximum_nominal_capacitance_pf=110,
        )
        split_with_cap_data = split.model_dump()
        split_with_cap_data["buses"][0]["endpoints"][0]["midpoint_capacitor"] = (
            midpoint_capacitor.model_dump()
        )
        split_with_capacitor = CanTerminationAnalysis.model_validate(split_with_cap_data)
        self.assertEqual(
            CanTerminationAnalysis.model_validate_json(split_with_capacitor.model_dump_json()),
            split_with_capacitor,
        )
        cap_paths = can_termination_netlist(
            split_paths, midpoint_capacitor=("C1", "100pF", "CAN_TERM_MID", "GND")
        )
        cap_checks = {
            item.id: item for item in can_termination_checks(split_with_capacitor, cap_paths)
        }
        cap_check_id = "can-termination/fieldbus/local/midpoint-capacitor"
        self.assertEqual(cap_checks[cap_check_id].status, "PASS")
        self.assertEqual(cap_checks[cap_check_id].observed, 100)

        for value in ("90pF", "110pF"):
            boundary_cap = can_termination_netlist(
                split_paths, midpoint_capacitor=("C1", value, "CAN_TERM_MID", "GND")
            )
            self.assertEqual(
                {
                    item.id: item
                    for item in can_termination_checks(split_with_capacitor, boundary_cap)
                }[cap_check_id].status,
                "PASS",
            )

        missing_cap_checks = {
            item.id: item
            for item in can_termination_checks(
                split_with_capacitor, can_termination_netlist(split_paths)
            )
        }
        self.assertEqual(missing_cap_checks[cap_check_id].status, "FAIL")
        self.assertIn("C1 is absent", missing_cap_checks[cap_check_id].detail)

        wrong_value = can_termination_netlist(
            split_paths, midpoint_capacitor=("C1", "120pF", "CAN_TERM_MID", "GND")
        )
        wrong_value_check = {
            item.id: item for item in can_termination_checks(split_with_capacitor, wrong_value)
        }[cap_check_id]
        self.assertEqual(wrong_value_check.status, "FAIL")
        self.assertIn("outside 90–110pF", wrong_value_check.detail)

        dnp_cap = can_termination_netlist(
            split_paths,
            dnp=("C1",),
            midpoint_capacitor=("C1", "100pF", "CAN_TERM_MID", "GND"),
        )
        self.assertIn(
            "C1 is DNP",
            {item.id: item for item in can_termination_checks(split_with_capacitor, dnp_cap)}[
                cap_check_id
            ].detail,
        )

        wrong_cap_identity = cap_paths.model_copy(
            update={
                "component_symbols": {**cap_paths.component_symbols, "C1": "Device:R"},
                "components": {
                    **cap_paths.components,
                    "C1": ComponentContract(value="100pF", footprint="Synthetic:WRONG"),
                },
            }
        )
        identity_check = {
            item.id: item
            for item in can_termination_checks(split_with_capacitor, wrong_cap_identity)
        }[cap_check_id]
        self.assertEqual(identity_check.status, "FAIL")
        self.assertIn("symbol is Device:R", identity_check.detail)
        self.assertIn("expected Synthetic:CAP", identity_check.detail)

        wrong_cap_net = cap_paths.model_copy(
            update={
                "nets": {
                    **cap_paths.nets,
                    "GND": (),
                    "OTHER": ("C1.2",),
                }
            }
        )
        net_check = {
            item.id: item for item in can_termination_checks(split_with_capacitor, wrong_cap_net)
        }[cap_check_id]
        self.assertEqual(net_check.status, "FAIL")
        self.assertIn("C1.2 is assigned to OTHER", net_check.detail)

        missing_cap_inventory = cap_paths.model_copy(
            update={
                "component_pin_numbers": {
                    reference: numbers
                    for reference, numbers in cap_paths.component_pin_numbers.items()
                    if reference != "C1"
                }
            }
        )
        self.assertIn(
            "C1 native pin inventory is missing",
            {
                item.id: item
                for item in can_termination_checks(split_with_capacitor, missing_cap_inventory)
            }[cap_check_id].detail,
        )

        wrong_topology = can_termination_netlist(
            {
                "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
                "R5": ("60R", "CAN_L", "CAN_H"),
            }
        )
        wrong_checks = {item.id: item for item in can_termination_checks(split, wrong_topology)}
        self.assertEqual(wrong_checks["can-termination/fieldbus/local"].status, "FAIL")

        external = CanTerminationAnalysis(
            basis="Synthetic bus is externally terminated in this assembly",
            buses=(
                CanTerminationBusRequirement(
                    id="fieldbus",
                    basis="Synthetic external termination declaration",
                    high_net="CAN_H",
                    low_net="CAN_L",
                    high_pins=("U1.1",),
                    low_pins=("U1.2",),
                    endpoints=(
                        CanTerminationEndpointRequirement(
                            id="remote",
                            basis="Remote equipment owns this bus-end terminator",
                            topology="external",
                            expected_dnp_resistors=("R9",),
                        ),
                    ),
                ),
            ),
        )
        external_netlist = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")}, dnp=("R9",))
        external_checks = {
            item.id: item for item in can_termination_checks(external, external_netlist)
        }
        self.assertEqual(
            external_checks["can-termination/fieldbus/remote/external-evidence"].status,
            "NOT_APPLICABLE",
        )
        self.assertEqual(
            external_checks["can-termination/fieldbus/remote/dnp-options"].status, "PASS"
        )

        misassigned_dnp = external_netlist.model_copy(
            update={
                "nets": {
                    "CAN_H": ("U1.1", "R9.1"),
                    "CAN_L": ("U1.2",),
                    "OTHER": ("R9.2",),
                }
            }
        )
        misassigned_dnp_checks = {
            item.id: item for item in can_termination_checks(external, misassigned_dnp)
        }
        self.assertEqual(
            misassigned_dnp_checks["can-termination/fieldbus/remote/dnp-options"].status,
            "FAIL",
        )

        external_bus_pin_missing = external_netlist.model_copy(
            update={
                "nets": {
                    "CAN_H": ("R9.1",),
                    "CAN_L": ("U1.2", "R9.2"),
                    "OTHER": ("U1.1",),
                }
            }
        )
        external_pin_checks = {
            item.id: item for item in can_termination_checks(external, external_bus_pin_missing)
        }
        self.assertEqual(external_pin_checks["can-termination/fieldbus/signal-pins"].status, "FAIL")
        self.assertEqual(
            external_pin_checks["can-termination/fieldbus/remote/external-evidence"].status,
            "NOT_APPLICABLE",
        )

        fitted_option = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")})
        fitted_checks = {item.id: item for item in can_termination_checks(external, fitted_option)}
        self.assertEqual(
            fitted_checks["can-termination/fieldbus/remote/dnp-options"].status, "FAIL"
        )
        self.assertEqual(fitted_checks["can-termination/fieldbus/unlisted-direct"].status, "FAIL")

    def test_can_termination_contract_rejects_incomplete_and_crossed_topologies(self) -> None:
        with self.assertRaisesRegex(ValueError, "Direct CAN termination needs one resistor"):
            CanTerminationEndpointRequirement(
                id="missing-part",
                basis="Invalid synthetic direct requirement",
                topology="direct",
            )
        with self.assertRaisesRegex(ValueError, "Only split CAN termination"):
            CanTerminationEndpointRequirement(
                id="direct-with-cap",
                basis="Invalid synthetic direct requirement",
                topology="direct",
                resistors=(
                    CanTerminationResistorRequirement(
                        reference="R1",
                        first_net="CAN_H",
                        second_net="CAN_L",
                        minimum_ohms=108,
                        maximum_ohms=132,
                    ),
                ),
                midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                    reference="C1",
                    expected_symbol="Device:C",
                    expected_footprint="Synthetic:CAP",
                    midpoint_pin="C1.1",
                    reference_pin="C1.2",
                    reference_net="GND",
                    minimum_nominal_capacitance_pf=90,
                    maximum_nominal_capacitance_pf=110,
                ),
            )
        with self.assertRaisesRegex(ValueError, "each bus net to one midpoint"):
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Invalid synthetic split requirement",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Two legs are required",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference="R4",
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference="R5",
                                first_net="CAN_L",
                                second_net="CAN_H",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                    ),
                ),
            )

    def test_grounding_accepts_distinct_domains_and_rejects_missing_wrong_extra_pins(self) -> None:
        spec, observed = self.ground()
        self.assertTrue(all(c.status == "PASS" for c in grounding_checks(spec, observed)))
        for nets in (
            {"GND": ("U1.2",), "AGND": ("U2.2",)},
            {"GND": ("U1.2", "J1.2", "U2.2")},
            {"GND": ("U1.2", "J1.2", "U1.3"), "AGND": ("U2.2",)},
            {"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",), "SHORT": ("U1.2",)},
        ):
            with self.subTest(nets=nets):
                changed = observed.model_copy(update={"nets": nets})
                self.assertTrue(any(c.status == "FAIL" for c in grounding_checks(spec, changed)))

    def test_new_component_requires_ground_review_or_explicit_exemption(self) -> None:
        spec, observed = self.ground()
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "R1": ComponentContract(value="1k", footprint=""),
                }
            }
        )
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "FAIL")
        spec = spec.model_copy(
            update={"exempt_components": {"R1": "Series resistor, no ground pin"}}
        )
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "PASS")
        spec = spec.model_copy(update={"exempt_components": {"U1": "Contradictory exemption"}})
        self.assertEqual(grounding_checks(spec, observed)[-1].status, "FAIL")

    def test_numbered_connector_returns_need_pinout_review_even_if_connector_is_covered(
        self,
    ) -> None:
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="Synthetic connector", footprint="")
                for ref in ("J1", "J2")
            },
            nets={
                "GND": ("J1.9", "J2.9"),
                "0V CTRL 1": ("J1.7",),
                "0V CTRL 2": ("J2.7",),
                "CTRL 1": ("J1.1",),
                "CTRL 2": ("J2.1",),
            },
        )
        groups = return_net_groups(observed)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0].nets), {"0V CTRL 1", "0V CTRL 2"})
        spec = GroundingAnalysis(
            basis="Independent synthetic connector pinout",
            domains=(GroundDomain(net="GND", pins=("J1.9", "J2.9")),),
        )
        checks = {row.id: row for row in grounding_checks(spec, observed)}
        self.assertEqual(checks["grounding/GND"].status, "PASS")
        self.assertEqual(checks["grounding/component-coverage"].status, "PASS")
        self.assertEqual(checks["grounding/return-net-review"].status, "FAIL")
        self.assertIn("J1.7", checks["grounding/return-net-review"].detail)
        pending = grounding_checks(
            AnalysisPending(mode="pending", reason="Connector pinout review pending"), observed
        )
        self.assertEqual(pending[0].status, "NOT_CONFIGURED")
        self.assertIn("0V CTRL 1", pending[0].detail)
        reviewed = spec.model_copy(
            update={
                "domains": (
                    *spec.domains,
                    GroundDomain(net="0V CTRL 1", pins=("J1.7",)),
                    GroundDomain(net="0V CTRL 2", pins=("J2.7",)),
                )
            }
        )
        self.assertTrue(all(row.status == "PASS" for row in grounding_checks(reviewed, observed)))

    def test_three_usb_signal_grounds_must_match_a_declared_common_net(self) -> None:
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="Synthetic part", footprint="")
                for ref in ("U1", "J1", "J2", "J3")
            },
            nets={
                "GND": ("U1.2",),
                "USB1_GND": ("J1.4",),
                "USB2_GND": ("J2.4",),
                "USB3_GND": ("J3.4",),
                "USB1_SHIELD": ("J1.5",),
                "USB2_SHIELD": ("J2.5",),
                "USB3_SHIELD": ("J3.5",),
                "USB1_DP": ("J1.3",),
            },
        )
        groups = return_net_groups(observed)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0].nets), {"USB1_GND", "USB2_GND", "USB3_GND"})
        spec = GroundingAnalysis(
            basis="Synthetic approved pinout requires one signal-ground domain",
            domains=(GroundDomain(net="GND", pins=("U1.2", "J1.4", "J2.4", "J3.4")),),
        )
        checks = {row.id: row for row in grounding_checks(spec, observed)}
        self.assertEqual(checks["grounding/GND"].status, "FAIL")
        self.assertEqual(checks["grounding/component-coverage"].status, "PASS")
        self.assertEqual(checks["grounding/return-net-review"].status, "FAIL")
        fixed = observed.model_copy(
            update={
                "nets": {
                    **{
                        name: pins
                        for name, pins in observed.nets.items()
                        if name not in {"GND", "USB1_GND", "USB2_GND", "USB3_GND"}
                    },
                    "GND": ("U1.2", "J1.4", "J2.4", "J3.4"),
                }
            }
        )
        self.assertFalse(return_net_groups(fixed))
        self.assertTrue(all(row.status == "PASS" for row in grounding_checks(spec, fixed)))

    def test_separate_serial_returns_pass_when_isolation_is_declared(self) -> None:
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="Synthetic part", footprint="")
                for ref in ("U1", "U2", "J1", "J2")
            },
            nets={
                "SERIAL_1_GND": ("U1.3", "J1.5"),
                "SERIAL_2_GND": ("U2.3", "J2.5"),
            },
        )
        self.assertEqual(set(return_net_groups(observed)[0].nets), {"SERIAL_1_GND", "SERIAL_2_GND"})
        isolated = GroundingAnalysis(
            basis="Synthetic approved pinout requires separate isolated returns",
            domains=(
                GroundDomain(net="SERIAL_1_GND", pins=("U1.3", "J1.5")),
                GroundDomain(net="SERIAL_2_GND", pins=("U2.3", "J2.5")),
            ),
        )
        self.assertTrue(all(row.status == "PASS" for row in grounding_checks(isolated, observed)))
        common = GroundingAnalysis(
            basis="Synthetic approved pinout requires common returns",
            domains=(GroundDomain(net="SERIAL_1_GND", pins=("U1.3", "J1.5", "U2.3", "J2.5")),),
        )
        checks = {row.id: row for row in grounding_checks(common, observed)}
        self.assertEqual(checks["grounding/SERIAL_1_GND"].status, "FAIL")
        self.assertEqual(checks["grounding/return-net-review"].status, "FAIL")

    def test_one_stray_usb_return_is_caught_by_the_declared_pinout(self) -> None:
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="Synthetic part", footprint="")
                for ref in ("U1", "J1", "J2", "J3")
            },
            nets={
                "GND": ("U1.2", "J1.4", "J2.4"),
                "USB3_GND": ("J3.4",),
            },
        )
        self.assertFalse(return_net_groups(observed))
        spec = GroundingAnalysis(
            basis="Synthetic approved pinout requires one signal-ground domain",
            domains=(GroundDomain(net="GND", pins=("U1.2", "J1.4", "J2.4", "J3.4")),),
        )
        checks = {row.id: row for row in grounding_checks(spec, observed)}
        self.assertEqual(checks["grounding/GND"].status, "FAIL")
        self.assertEqual(checks["grounding/component-coverage"].status, "PASS")
        self.assertNotIn("grounding/return-net-review", checks)

    def test_protocol_numbers_and_shields_are_not_return_group_indices(self) -> None:
        observed = NetlistContract(
            components={},
            nets={
                "RS232_GND": ("J1.5",),
                "RS485_GND": ("J2.5",),
                "USB1_SHIELD": ("J3.5",),
                "USB2_SHIELD": ("J4.5",),
            },
        )
        self.assertFalse(return_net_groups(observed))

    def test_repeated_connector_power_pin_missing_from_net_requires_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="synthetic-connectors-") as temporary:
            netlist = Path(temporary) / "netlist.xml"
            netlist.write_text(
                "<export><components>"
                + "".join(
                    f'<comp ref="J{index}"><value>Synthetic port</value>'
                    '<libsource lib="Synthetic" part="Port"/>'
                    '<units><unit name="A"><pins><pin num="1"/><pin num="2"/>'
                    "</pins></unit></units></comp>"
                    for index in (1, 2, 3)
                )
                + '</components><libparts><libpart lib="Synthetic" part="Port">'
                '<pins><pin num="1" name="PWR" type="passive"/>'
                '<pin num="2" name="GND" type="passive"/></pins></libpart></libparts>'
                '<nets><net name="+5V"><node ref="J1" pin="1"/>'
                '<node ref="J2" pin="1"/></net>'
                '<net name="GND"><node ref="J1" pin="2"/>'
                '<node ref="J2" pin="2"/><node ref="J3" pin="2"/></net>'
                '<net name="unconnected-(J3-PWR-Pad1)"><node ref="J3" pin="1"/></net>'
                "</nets></export>",
                encoding="utf-8",
            )
            observed = read_netlist(netlist)
        self.assertEqual(observed.unconnected_nets, {"unconnected-(J3-PWR-Pad1)": ("J3.1",)})
        self.assertEqual(observed.pin_functions["J3.1"], "PWR")
        groups = similar_connector_pin_groups(observed)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].function, "PWR")
        self.assertEqual(groups[0].pins["J3.1"], ())
        spec = PinConnectivityAnalysis(
            basis="Approved synthetic three-port power pinout",
            rules=(
                PinRelationshipRule(
                    id="port-power",
                    basis="All three connector power pins share the approved rail",
                    topology="common_net",
                    pins=("J1.1", "J2.1", "J3.1"),
                    net="+5V",
                ),
            ),
        )
        self.assertEqual(pin_relationship_checks(spec, observed)[0].status, "FAIL")
        connected = observed.model_copy(
            update={"nets": {**observed.nets, "+5V": ("J1.1", "J2.1", "J3.1")}}
        )
        self.assertFalse(similar_connector_pin_groups(connected))
        self.assertEqual(pin_relationship_checks(spec, connected)[0].status, "PASS")
        wrong_rail = connected.model_copy(
            update={"nets": {"+12V": connected.nets["+5V"], "GND": connected.nets["GND"]}}
        )
        self.assertEqual(pin_relationship_checks(spec, wrong_rail)[0].status, "FAIL")
        unused = PinConnectivityAnalysis(
            basis="Synthetic connector pin disposition",
            rules=(
                PinRelationshipRule(
                    id="unpopulated-power",
                    basis="J3.1 is intentionally unused on this approved variant",
                    topology="unconnected",
                    pins=("J3.1",),
                ),
            ),
        )
        self.assertEqual(pin_relationship_checks(unused, observed)[0].status, "PASS")
        self.assertEqual(pin_relationship_checks(unused, connected)[0].status, "FAIL")

    def test_same_connector_power_labels_can_require_separate_nets(self) -> None:
        observed = NetlistContract(
            components={
                ref: ComponentContract(value="Synthetic port", footprint="") for ref in ("J1", "J2")
            },
            nets={"PORT1_PWR": ("J1.1",), "PORT2_PWR": ("J2.1",)},
            component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
            pin_functions={"J1.1": "PWR", "J2.1": "PWR"},
        )
        self.assertEqual(len(similar_connector_pin_groups(observed)), 1)
        separate = PinConnectivityAnalysis(
            basis="Approved independently switched outputs",
            rules=(
                PinRelationshipRule(
                    id="independent-power",
                    basis="Each connector has an independent output",
                    topology="separate_nets",
                    pins=("J1.1", "J2.1"),
                ),
            ),
        )
        self.assertEqual(pin_relationship_checks(separate, observed)[0].status, "PASS")
        tied = observed.model_copy(update={"nets": {"PORT1_PWR": ("J1.1", "J2.1")}})
        self.assertEqual(pin_relationship_checks(separate, tied)[0].status, "FAIL")
        with self.assertRaises(ValueError):
            PinRelationshipRule(
                id="invalid",
                basis="Contradictory rule",
                topology="separate_nets",
                pins=("J1.1", "J2.1"),
                net="+5V",
            )

    def test_pin_relationship_can_require_an_intentionally_unconnected_pin(self) -> None:
        observed = NetlistContract(
            components={"J1": ComponentContract(value="Synthetic port", footprint="")},
            nets={"SIGNAL": ("J1.1",)},
            component_pin_numbers={"J1": ("1", "2")},
        )
        requirement = PinConnectivityAnalysis(
            basis="Approved synthetic connector pin disposition",
            rules=(
                PinRelationshipRule(
                    id="reserved-pin",
                    basis="Pin 2 is intentionally unused on this assembly",
                    topology="unconnected",
                    pins=("J1.2",),
                ),
            ),
        )
        self.assertEqual(pin_relationship_checks(requirement, observed)[0].status, "PASS")

        newly_connected = observed.model_copy(
            update={"nets": {**observed.nets, "SIGNAL": ("J1.1", "J1.2")}}
        )
        changed = pin_relationship_checks(requirement, newly_connected)[0]
        self.assertEqual(changed.status, "FAIL")
        self.assertIn("J1.2", changed.detail)

        stale_pin = requirement.model_copy(
            update={"rules": (requirement.rules[0].model_copy(update={"pins": ("J1.3",)}),)}
        )
        stale = pin_relationship_checks(stale_pin, observed)[0]
        self.assertEqual(stale.status, "FAIL")
        self.assertIn("unknown symbol pins=['J1.3']", stale.detail)

        with self.assertRaises(ValueError):
            PinRelationshipRule(
                id="single-common-pin",
                basis="A common relationship requires multiple pins",
                topology="common_net",
                pins=("J1.1",),
            )
        with self.assertRaises(ValueError):
            PinRelationshipRule(
                id="unused-with-net",
                basis="An unused pin cannot have a required net",
                topology="unconnected",
                pins=("J1.2",),
                net="GND",
            )

    def test_misleading_return_names_need_reasoned_exceptions_and_no_stale_waiver(self) -> None:
        observed = NetlistContract(
            components={"J1": ComponentContract(value="Synthetic connector", footprint="")},
            nets={"GND": ("J1.9",), "RETURN STATUS 1": ("J1.1",), "RETURN STATUS 2": ("J1.2",)},
        )
        spec = GroundingAnalysis(
            basis="Synthetic pinout distinguishes logic status from ground",
            domains=(GroundDomain(net="GND", pins=("J1.9",)),),
            reviewed_return_exceptions={
                "RETURN STATUS 1": "Logic status, not a return",
                "RETURN STATUS 2": "Logic status, not a return",
            },
        )
        self.assertTrue(all(row.status == "PASS" for row in grounding_checks(spec, observed)))
        stale = spec.model_copy(
            update={
                "reviewed_return_exceptions": {
                    **spec.reviewed_return_exceptions,
                    "RETURN STATUS 3": "Old pinout",
                }
            }
        )
        self.assertEqual(
            next(
                row
                for row in grounding_checks(stale, observed)
                if row.id.endswith("return-net-review")
            ).status,
            "FAIL",
        )
        with self.assertRaises(ValueError):
            GroundingAnalysis(
                basis="Conflicting synthetic declaration",
                domains=(GroundDomain(net="GND", pins=("J1.9",)),),
                reviewed_return_exceptions={"GND": "Contradiction"},
            )

    def test_strict_contract_round_trip_and_schema(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        path = root / ISLAND / "tests/electrical.json"
        self.assertEqual(read_model(path, ElectricalAnalysisContract), contract)
        schema = json.loads(expected_outputs(root)["schemas/electrical-analysis-v1.schema.json"])
        self.assertEqual(schema, ElectricalAnalysisContract.model_json_schema())
        for key, value in (("schema_version", "2"), ("unknown", True), ("ngspice_version", 47)):
            raw = json.loads(contract.model_dump_json())
            raw[key] = value
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                read_model(path, ElectricalAnalysisContract)

    def test_invalid_ground_duplicates_windows_limits_and_model_bindings(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        mutations = (
            lambda d: d["grounding"]["domains"][0]["pins"].append("R1.2"),
            lambda d: d["power"]["startup"][0]["measures"][0].update(minimum=6.0),
            lambda d: d["power"]["startup"][0].update(step_s=1.0),
            lambda d: d["power"]["startup"][0].update(source_sha256={}),
            lambda d: d["high_frequency"]["waveforms"][0].update(step_s=1e-7),
            lambda d: d["high_frequency"]["sweeps"][0].update(stop_hz=1.0),
            lambda d: d["power"]["startup"][0]["measures"][0].update(expression="v(out)\nquit"),
            lambda d: d["power"]["steady_state"][0].update(id="startup"),
            lambda d: d["power"]["steady_state"][0]["measures"][1].update(unit="A"),
        )
        for mutation in mutations:
            raw = json.loads(contract.model_dump_json())
            mutation(raw)
            with self.assertRaises(ValueError):
                ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_budgets_reject_steady_peak_and_excess_peak_duration(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert isinstance(spec, PowerAnalysis)
        self.assertTrue(all(c.status == "PASS" for c in power_budget_checks(spec)))
        for field, value, expected in (
            ("continuous_limit_a", 0.01, "steady-current"),
            ("peak_limit_a", 1.0, "startup-current"),
            ("peak_duration_limit_s", 1e-5, "startup-duration"),
        ):
            changed = spec.model_copy(
                update={"rails": (spec.rails[0].model_copy(update={field: value}),)}
            )
            failures = [c.id for c in power_budget_checks(changed) if c.status == "FAIL"]
            self.assertIn(f"power/supply/{expected}", failures)

    def test_zero_startup_current_cannot_hide_steady_load(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert isinstance(spec, PowerAnalysis)
        load = spec.rails[0].loads[0].model_copy(update={"startup_a": 0.0})
        changed = spec.model_copy(
            update={"rails": (spec.rails[0].model_copy(update={"loads": (load,)}),)}
        )
        check = next(c for c in power_budget_checks(changed) if c.id.endswith("startup-current"))
        self.assertEqual(check.observed, 0.05)

    def test_binding_rejects_changed_source_model_wrong_project_and_escaping_contract(self) -> None:
        for kind in ("source", "model", "identity", "path"):
            with self.subTest(kind=kind):
                root = self.stage()
                contract = install_fixture(root)
                config = selected_config(root, PROJECT)
                self.assertEqual(policy_issues(root, config), ())
                if kind == "source":
                    target = root / config.required_inputs[0]
                    target.write_bytes(target.read_bytes() + b"\n")
                elif kind == "model":
                    target = root / ISLAND / "tests/electrical/startup.cir"
                    target.write_text(target.read_text().replace("100u", "200u"))
                elif kind == "identity":
                    write_model(
                        root / config.electrical,
                        contract.model_copy(update={"project_id": "wrong"}),
                    )
                else:
                    config = config.model_copy(update={"electrical": "../elsewhere.json"})
                self.assertTrue(policy_issues(root, config))

    def test_undeclared_includes_control_code_and_unused_models_rejected(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        target = root / case.deck
        for text in (
            'title\n.include "hidden.lib"\n.end\n',
            "title\n.control\nquit\n.endc\n.end\n",
            'title\n.lib "hidden.lib" section\n.end\n',
            "title\n.end\nR1 a 0 1k\n",
        ):
            target.write_text(text)
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)

    def test_simulator_failure_missing_duplicate_nonfinite_and_out_of_limit_measurements(
        self,
    ) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        for stdout in (
            "",
            "check0 = nan",
            "check0 = 2\ncheck0 = 3",
            "check0 = 9",
            "check0 = 2\nError: transient failed",
        ):
            command = CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout=stdout
            )
            self.assertTrue(any(c.status == "FAIL" for c in measured_checks(case, command)))
        command = CommandEvidence(
            argv=("ngspice",), started_utc="fixture", returncode=0, stdout="check0 = 4.95"
        )
        self.assertEqual(measured_checks(case, command)[0].status, "PASS")
        deck = simulation_deck(root, case)
        self.assertIn("tran 9.999", deck)
        self.assertIn("set measureprec=15", deck)
        self.assertIn("set rawfileprec=17", deck)

    def test_missing_or_wrong_simulator_does_not_pass(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        write_model(
            root / ISLAND / "tests/electrical.json", contract.model_copy(update={"grounding": NA})
        )
        report = analyze(root, PROJECT, ngspice="missing-electrical-simulator")
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any(c.status == "NOT_RUN" for c in report.checks))
        self.assertTrue((Path(report.run_directory) / "ngspice-version.command.json").is_file())
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout="ngspice-46"
            ),
        ):
            self.assertRaisesRegex(
                ValueError,
                "Exact ngspice",
                simulator_version,
                Path(report.run_directory),
                "ngspice",
                "47",
            )

    def test_unconfigured_cli_is_explicit_nonzero_and_writes_a_receipt(self) -> None:
        root = self.stage()
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical",
                "--root",
                str(root),
                "--project",
                PROJECT,
                "--format",
                "json",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        self.assertEqual(json.loads(command.stdout)["status"], "NOT_CONFIGURED")

    def test_bound_inputs_and_policy_are_rechecked_after_execution(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        contract = contract.model_copy(update={"power": NA, "high_frequency": NA, "grounding": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        config = selected_config(root, PROJECT)
        self.assertIsNotNone(load_analysis(root, config))
        before = bound_inputs(root, config, contract)
        with patch("kicad_tooling.hwrepo.electrical_runner.bound_inputs", side_effect=[before, {}]):
            report = analyze(root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("changed during", report.checks[-1].detail)

    def test_timeout_receipt_and_missing_waveforms_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        output = root / "build/spice-test"
        output.mkdir(parents=True)
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=124, error="Timed out"
            ),
        ):
            _, checks = run_case(root, output, "ngspice", contract.power.startup[0])
        self.assertTrue(all(c.status == "FAIL" for c in checks))
        self.assertTrue((output / "startup/ngspice.command.json").is_file())

    def test_waveform_parser_rejects_truncated_nonfinite_and_uncovered_data(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        raw = root / "waveform.raw"
        content = "Title: test\nFlags: real\nNo. Variables: 2\nNo. Points: 3\nVariables:\n0 time time\n1 v(out) voltage\nValues:\n0 0\n0\n1 0.001\n4.9\n2 0.005\n5\n"
        raw.write_text(content)
        self.assertTrue(all(c.status == "PASS" for c in waveform_checks(raw, case)))
        for changed in (
            content.replace("2 0.005\n5\n", ""),
            content.replace("4.9", "nan"),
            content.replace("1 0.001", "1 -0.001"),
        ):
            raw.write_text(changed)
            with self.assertRaises(ValueError):
                waveform_checks(raw, case)
        raw.write_text(content.replace("0.001", "0.0001").replace("0.005", "0.0005"))
        self.assertTrue(any(c.status == "FAIL" for c in waveform_checks(raw, case)))

    def test_recursive_escaping_and_unlisted_model_includes_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        target = root / case.deck
        for include in ("startup.cir", "../other.cir", "/tmp/other.cir"):
            target.write_text(f'title\n.include "{include}"\n.end\n')
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)
        included = target.with_name("passive.lib")
        included.write_text("R1 in out 10\n")
        target.write_text('title\n.include "passive.lib"\n.end\n')
        case = case.model_copy(
            update={
                "model_sha256": {
                    case.deck: digest(target),
                    included.relative_to(root).as_posix(): digest(included),
                }
            }
        )
        self.assertIn("R1 in out 10", expanded_deck(root, case))
        target.write_text("title\nR1 in out 1\n.end\n")
        case = case.model_copy(
            update={"model_sha256": {**case.model_sha256, case.deck: digest(target)}}
        )
        with self.assertRaisesRegex(ValueError, "Unused model"):
            expanded_deck(root, case)

    def test_portable_gate_rejects_an_overload_and_cli_cannot_bypass_model_hashes(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        overloaded = contract.power.model_copy(
            update={
                "rails": (
                    contract.power.rails[0].model_copy(update={"continuous_limit_a": 0.001}),
                ),
            }
        )
        write_model(
            root / ISLAND / "tests/electrical.json",
            contract.model_copy(update={"power": overloaded}),
        )
        from kicad_tooling.ci import project_static_pipeline

        result = project_static_pipeline(root, (PROJECT,))
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("steady-current" in issue for issue in result.registry.issues))
        write_model(root / ISLAND / "tests/electrical.json", contract)
        model = root / contract.power.startup[0].deck
        model.write_text(model.read_text() + "\n")
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.ci",
                "--root",
                str(root),
                "--electrical",
                "--project",
                PROJECT,
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        report = json.loads(command.stdout)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("stale reviewed model", report["projects"][0]["checks"][-1]["detail"])

    def test_combined_verification_cannot_pass_a_failed_electrical_lane(self) -> None:
        from kicad_tooling.hwrepo.models import ElectricalAnalysisReport, ElectricalCheck
        from kicad_tooling.verify import verify
        from tests.test_verify import VerifyTests, native_summary

        root = self.stage().resolve()
        contract = install_fixture(root).model_copy(update={"power": NA, "high_frequency": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        failed = ElectricalAnalysisReport(
            project_id=PROJECT,
            status="FAIL",
            run_directory=str(root / "build/simulation"),
            checks=(ElectricalCheck(id="grounding", status="FAIL", detail="Missing pin U1.2"),),
        )
        with (
            VerifyTests.runner_environment("10.0.0"),
            patch("kicad_tooling.verify.check_all", return_value=native_summary()),
            patch(
                "kicad_tooling.hwrepo.electrical_runner.analyze", return_value=failed
            ) as simulation,
        ):
            result = verify(
                root, PROJECT, depth="electrical", runner="local", ngspice="approved-ngspice"
            )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.electrical, failed)
        self.assertEqual(simulation.call_args.args[-1], "approved-ngspice")
        self.assertIn("electrical", result.next_actions[0])


if __name__ == "__main__":
    unittest.main()
