"""Synthetic SPI contract requirements and netlist fixtures."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.spi_models import (
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
