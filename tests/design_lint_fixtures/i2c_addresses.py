"""Shared synthetic address-map inputs for I2C design-lint tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    I2cAddressBitRequirement,
    I2cAddressMap,
    I2cAddressSegmentRequirement,
    I2cResponderAddressRequirement,
    NetlistContract,
)

_NETLIST_HASH = "b" * 64


def responder(
    reference: str,
    *,
    address: int | None = 0x50,
    strap: bool = True,
    segment: str = "MAIN",
) -> tuple[str, I2cResponderAddressRequirement]:
    address_bits = (
        (
            I2cAddressBitRequirement(
                bit=0,
                pin=f"{reference}.3",
                function="A0",
                low_net="GND",
                high_net="+3V3",
            ),
        )
        if strap
        else ()
    )
    mode = "strapped" if strap else "fixed" if address is not None else "dynamic"
    return (
        segment,
        I2cResponderAddressRequirement(
            reference=reference,
            expected_symbol="Synthetic:EEPROM",
            sda_pin=f"{reference}.1",
            scl_pin=f"{reference}.2",
            mode=mode,
            address=address,
            address_bits=address_bits,
            basis=f"Synthetic reviewed address basis for {reference}",
        ),
    )


def address_map(*responders: tuple[str, I2cResponderAddressRequirement]) -> I2cAddressMap:
    grouped: dict[str, list[I2cResponderAddressRequirement]] = {}
    for segment, requirement in responders:
        grouped.setdefault(segment, []).append(requirement)
    return I2cAddressMap(
        basis="Synthetic segment and responder map",
        segments=tuple(
            I2cAddressSegmentRequirement(
                id=segment,
                sda_net=f"{segment}_SDA",
                scl_net=f"{segment}_SCL",
                responders=tuple(items),
            )
            for segment, items in sorted(grouped.items())
        ),
    )


def address_netlist(
    specification: I2cAddressMap,
    *,
    strap_values: dict[str, int | None] | None = None,
    symbol_overrides: dict[str, str] | None = None,
    function_overrides: dict[str, str] | None = None,
    misplaced_pins: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    strap_values = strap_values or {}
    symbol_overrides = symbol_overrides or {}
    function_overrides = function_overrides or {}
    misplaced_pins = misplaced_pins or {}
    components: dict[str, ComponentContract] = {}
    symbols: dict[str, str] = {}
    functions: dict[str, str] = {}
    pin_numbers: dict[str, tuple[str, ...]] = {}
    nets: dict[str, list[str]] = {}

    for segment in specification.segments:
        for requirement in segment.responders:
            reference = requirement.reference
            components[reference] = ComponentContract(value="EEPROM", footprint="Synthetic:SOIC8")
            symbols[reference] = symbol_overrides.get(reference, requirement.expected_symbol)
            all_pins = {requirement.sda_pin, requirement.scl_pin}
            all_pins.update(item.pin for item in requirement.address_bits)
            pin_numbers[reference] = tuple(
                sorted((pin.rsplit(".", 1)[1] for pin in all_pins), key=int)
            )
            functions[requirement.sda_pin] = function_overrides.get(requirement.sda_pin, "SDA")
            functions[requirement.scl_pin] = function_overrides.get(requirement.scl_pin, "SCL")
            nets.setdefault(misplaced_pins.get(requirement.sda_pin, segment.sda_net), []).append(
                requirement.sda_pin
            )
            nets.setdefault(misplaced_pins.get(requirement.scl_pin, segment.scl_net), []).append(
                requirement.scl_pin
            )
            for bit in requirement.address_bits:
                functions[bit.pin] = function_overrides.get(bit.pin, bit.function)
                value = strap_values.get(reference, 0)
                assigned_net = (
                    None if value is None else bit.low_net if value == 0 else bit.high_net
                )
                if assigned_net is not None:
                    nets.setdefault(misplaced_pins.get(bit.pin, assigned_net), []).append(bit.pin)

    resistor_number = 1
    for segment in specification.segments:
        for signal_net in (segment.sda_net, segment.scl_net):
            reference = f"R{resistor_number}"
            resistor_number += 1
            components[reference] = ComponentContract(value="4.7k", footprint="Synthetic:RES")
            pin_numbers[reference] = ("1", "2")
            nets.setdefault(signal_net, []).append(f"{reference}.1")
            nets.setdefault("+3V3", []).append(f"{reference}.2")

    return NetlistContract(
        components=components,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        component_pin_numbers=pin_numbers,
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_HASH) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i2c-addresses",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )


def unmapped_responder_netlist(reference: str = "U1") -> NetlistContract:
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic target", footprint="Synthetic:SOIC8"),
            "R1": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
            "R2": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
        },
        nets={
            "SDA_BUS": (f"{reference}.1", "R1.1"),
            "SCL_BUS": (f"{reference}.2", "R2.1"),
            "+3V3": ("R1.2", "R2.2"),
        },
        component_symbols={reference: "Synthetic:Target"},
        pin_functions={f"{reference}.1": "SDA", f"{reference}.2": "I2C_SCL"},
        component_pin_numbers={reference: ("1", "2")},
    )
