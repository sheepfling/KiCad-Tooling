"""Synthetic design-lint inputs for focused regression suites."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
    NetlistContract,
)


def spi_peer_voltage_netlist(
    *,
    output_rail: str = "+5V",
    input_rail: str = "+3V3",
    input_extra_supply: bool = False,
    unconnected_input_supply: bool = False,
    missing_pin_types: bool = False,
    signal_function: str = "MOSI",
    all_signal_function: str | None = None,
    output_type: str = "output",
    input_type: str = "input",
    dnp: tuple[str, ...] = (),
    level_shifted: bool = False,
) -> NetlistContract:
    """Build synthetic SPI endpoints and direct-peer boundary controls."""
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Package:Controller"),
        "U2": ComponentContract(value="Synthetic peripheral", footprint="Package:Peripheral"),
    }
    component_pin_numbers = {
        "U1": ("1", "2", "8", "9"),
        "U2": ("1", "2", "8", *(("10",) if input_extra_supply else ()), "9"),
    }
    pin_functions = {
        "U1.1": all_signal_function or "SCK",
        "U1.2": all_signal_function or signal_function,
        "U1.8": "VDD",
        "U1.9": "GND",
        "U2.1": all_signal_function or "SCK",
        "U2.2": all_signal_function or signal_function,
        "U2.8": "VDD",
        "U2.9": "GND",
    }
    pin_electrical_types = {
        "U1.1": output_type,
        "U1.2": output_type,
        "U1.8": "power_in",
        "U1.9": "power_in",
        "U2.1": input_type,
        "U2.2": input_type,
        "U2.8": "power_in",
        "U2.9": "power_in",
    }
    if level_shifted:
        components["U3"] = ComponentContract(
            value="Synthetic dual-supply translator", footprint="Package:Translator"
        )
        component_symbols = {
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:Peripheral",
            "U3": "Synthetic:LevelTranslator",
        }
        component_pin_numbers["U3"] = ("1", "2", "3", "4", "5", "6", "7")
        pin_functions.update(
            {
                "U3.1": "A_SCK",
                "U3.2": "B_SCK",
                "U3.3": "A_MOSI",
                "U3.4": "B_MOSI",
                "U3.5": "VCCA",
                "U3.6": "VCCB",
                "U3.7": "GND",
            }
        )
        pin_electrical_types.update(
            {
                "U3.1": "input",
                "U3.2": "output",
                "U3.3": "input",
                "U3.4": "output",
                "U3.5": "power_in",
                "U3.6": "power_in",
                "U3.7": "power_in",
            }
        )
    else:
        component_symbols = {
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:Peripheral",
        }
    nets: dict[str, tuple[str, ...]] = {
        output_rail: ("U1.8", *(("U3.5",) if level_shifted else ())),
        "GND": ("U1.9", "U2.9", *(("U3.7",) if level_shifted else ())),
    }
    if level_shifted:
        nets.update(
            {
                input_rail: ("U2.8", "U3.6"),
                "SPI_SCK_CONTROLLER": ("U1.1", "U3.1"),
                "SPI_SCK_PERIPHERAL": ("U3.2", "U2.1"),
                "SPI_MOSI_CONTROLLER": ("U1.2", "U3.3"),
                "SPI_MOSI_PERIPHERAL": ("U3.4", "U2.2"),
            }
        )
    else:
        nets.update(
            {
                "SPI_SCK": ("U1.1", "U2.1"),
                "SPI_MOSI": ("U1.2", "U2.2"),
            }
        )
    if not unconnected_input_supply and "U2.8" not in nets.get(input_rail, ()):
        nets[input_rail] = (*nets.get(input_rail, ()), "U2.8")
    if input_extra_supply:
        pin_functions["U2.10"] = "VDDIO"
        pin_electrical_types["U2.10"] = "power_in"
        nets["+1V8"] = ("U2.10",)
    if missing_pin_types:
        pin_electrical_types = {}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def spi_peer_voltage_map(
    pins: tuple[tuple[str, str], ...] = (("U1.1", "U2.1"),),
    *,
    with_limits: bool = True,
    receiver_absolute_maximum_v: float = 3.6,
) -> DigitalPeerVoltageAnalysis:
    links = []
    for index, (output_pin, input_pin) in enumerate(pins, start=1):
        net = "SPI_SCK" if output_pin.endswith(".1") else "SPI_MOSI"
        links.append(
            DigitalPeerVoltageLink(
                id=f"spi-peer-{index}",
                basis="Synthetic exact SPI peer map with datasheet limits",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:Controller",
                    footprint="Package:Controller",
                    pin=output_pin,
                    net=net,
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:Peripheral",
                    footprint="Package:Peripheral",
                    pin=input_pin,
                    net=net,
                ),
                output_limits=(
                    DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.4,
                        high_maximum_v=5.0,
                        source="Synthetic controller datasheet Rev A, Table 8",
                        conditions="VDD=5 V, stated load, full temperature range",
                    )
                    if with_limits
                    else None
                ),
                input_limits=(
                    DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=receiver_absolute_maximum_v,
                        source="Synthetic peripheral datasheet Rev B, Table 4",
                        conditions="VDD=3.3 V, full temperature range",
                    )
                    if with_limits
                    else None
                ),
            )
        )
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic exact direct-peer voltage map for lint control coverage",
        links=tuple(links),
    )


def serial_peer_voltage_netlist(
    *,
    output_rail: str = "+5V",
    input_rail: str = "+3V3",
    output_function: str = "UART1_TX",
    input_function: str = "UART1_RX",
    output_type: str = "output",
    input_type: str = "input",
    input_extra_supply: bool = False,
    unconnected_input_supply: bool = False,
    missing_pin_types: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two synthetic UART endpoints and source-bound evidence controls."""
    u2_numbers = ("1", "8", *(("10",) if input_extra_supply else ()), "9")
    pin_functions = {
        "U1.1": output_function,
        "U1.8": "VDD",
        "U1.9": "GND",
        "U2.1": input_function,
        "U2.8": "VDD",
        "U2.9": "GND",
    }
    pin_types = {
        "U1.1": output_type,
        "U1.8": "power_in",
        "U1.9": "power_in",
        "U2.1": input_type,
        "U2.8": "power_in",
        "U2.9": "power_in",
    }
    nets: dict[str, tuple[str, ...]] = {
        "UART_TX": ("U1.1", "U2.1"),
        output_rail: ("U1.8",),
        "GND": ("U1.9", "U2.9"),
    }
    if not unconnected_input_supply:
        nets[input_rail] = (*nets.get(input_rail, ()), "U2.8")
    if input_extra_supply:
        pin_functions["U2.10"] = "VDDIO"
        pin_types["U2.10"] = "power_in"
        nets["+1V8"] = ("U2.10",)
    if missing_pin_types:
        pin_types = {}
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers={"U1": ("1", "8", "9"), "U2": u2_numbers},
    )


def serial_peer_voltage_translator_netlist() -> NetlistContract:
    """Model a UART link whose endpoints meet only through a level translator."""
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
            "U3": ComponentContract(
                value="Synthetic UART level translator", footprint="Package:UART-XLAT"
            ),
        },
        nets={
            "UART_A_TX": ("U1.1", "U3.1"),
            "UART_B_TX": ("U3.2", "U2.1"),
            "+5V": ("U1.8", "U3.3"),
            "+3V3": ("U2.8", "U3.4"),
            "GND": ("U1.9", "U2.9", "U3.5"),
        },
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
            "U3": "Synthetic:UartLevelTranslator",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "UART1_RX",
            "U2.8": "VDD",
            "U2.9": "GND",
            "U3.1": "A_TX",
            "U3.2": "B_RX",
            "U3.3": "VCCA",
            "U3.4": "VCCB",
            "U3.5": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "input",
            "U2.8": "power_in",
            "U2.9": "power_in",
            "U3.1": "input",
            "U3.2": "output",
            "U3.3": "power_in",
            "U3.4": "power_in",
            "U3.5": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "8", "9"),
            "U2": ("1", "8", "9"),
            "U3": ("1", "2", "3", "4", "5"),
        },
    )


def serial_peer_voltage_map(*, with_limits: bool = True) -> DigitalPeerVoltageAnalysis:
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic exact UART peer map with datasheet limits",
        links=(
            DigitalPeerVoltageLink(
                id="uart-tx-rx",
                basis="Controller TX directly drives receiver RX",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:UartTransmitter",
                    footprint="Package:UART-TX",
                    pin="U1.1",
                    net="UART_TX",
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:UartReceiver",
                    footprint="Package:UART-RX",
                    pin="U2.1",
                    net="UART_TX",
                ),
                output_limits=(
                    DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.4,
                        high_maximum_v=5.0,
                        source="Synthetic controller datasheet Rev A, Table 8",
                        conditions="VDD=5 V, stated load, full temperature range",
                    )
                    if with_limits
                    else None
                ),
                input_limits=(
                    DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=3.6,
                        source="Synthetic receiver datasheet Rev B, Table 4",
                        conditions="VDD=3.3 V, full temperature range",
                    )
                    if with_limits
                    else None
                ),
            ),
        ),
    )


def header_only_spi_uart_netlist() -> NetlistContract:
    """Model external bus headers that are not direct on-board IC peers."""
    references = ("J1", "J2")
    pin_numbers = ("1", "2", "3", "4", "5", "6")
    nets = {
        "SPI_SCK": ("J1.1", "J2.1"),
        "SPI_MOSI": ("J1.2", "J2.2"),
        "UART0_TX": ("J1.3", "J2.3"),
        "UART0_RX": ("J1.4", "J2.4"),
        "+5V": ("J1.5",),
        "+3V3": ("J2.5",),
        "GND": ("J1.6", "J2.6"),
    }
    pin_functions = {
        "J1.1": "SCK",
        "J1.2": "MOSI",
        "J1.3": "UART0_TX",
        "J1.4": "UART0_RX",
        "J1.5": "VCC",
        "J1.6": "GND",
        "J2.1": "SCK",
        "J2.2": "MOSI",
        "J2.3": "UART0_TX",
        "J2.4": "UART0_RX",
        "J2.5": "VCC",
        "J2.6": "GND",
    }
    electrical_types = {
        "J1.1": "output",
        "J1.2": "output",
        "J1.3": "output",
        "J1.4": "input",
        "J1.5": "power_in",
        "J1.6": "power_in",
        "J2.1": "input",
        "J2.2": "input",
        "J2.3": "input",
        "J2.4": "output",
        "J2.5": "power_in",
        "J2.6": "power_in",
    }
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="External bus header",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
            )
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:ExternalBusHeader" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers={reference: pin_numbers for reference in references},
    )
