"""Translate unconnected protocol-pin observations."""

from __future__ import annotations

from .bus_signal_roles import unconnected_interface_pins
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_unconnected_pins import unconnected_serial_function_pins
from .spi_unconnected_data_pins import unconnected_spi_data_function_pins
from .usb_unconnected_data import unconnected_usb_data_pins


def unconnected_interface_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Build review prompts for unconnected protocol pins."""
    found: list[Candidate] = []
    for pin in unconnected_interface_pins(observed):
        if pin.protocol == "i2c":
            rule_id: DesignLintRuleId = "bus.i2c_unconnected_pin"
            description = "I²C signal"
        elif pin.protocol == "spi":
            rule_id = "bus.spi_unconnected_chip_select"
            description = "SPI chip-select"
        elif pin.protocol == "usb_c":
            rule_id = "bus.usb_c_unconnected_cc_pin"
            description = "USB-C configuration-channel"
        else:
            rule_id = "bus.can_unconnected_line"
            description = "CANH/CANL line"
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This named {description} pin has no net assignment. Review whether it is "
                    "intentionally unused or a connection is missing."
                ),
                evidence={pin.pin: (), "function": (pin.function,)},
            )
        )
    for pin in unconnected_usb_data_pins(observed):
        side = "D+" if pin.side == "positive" else "D−"
        port = f" port {pin.port_index}" if pin.port_index is not None else ""
        found.append(
            Candidate(
                rule_id="bus.usb_unconnected_data_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This native USB 2.0 {side}{port} data pin has no net assignment. Review "
                    "whether the interface is intentionally unused or a connection is missing. "
                    "The pin function alone does not establish bus membership or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "USB_data_side": (side,),
                    **(
                        {"USB_data_port_index": (pin.port_index,)}
                        if pin.port_index is not None
                        else {}
                    ),
                },
            )
        )
    for pin in unconnected_spi_data_function_pins(observed):
        family = "MOSI-family" if pin.role == "input" else "MISO-family"
        found.append(
            Candidate(
                rule_id="bus.spi_unconnected_data_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    "This native SPI data-function pin has no net assignment while another "
                    "data pin on the same fitted IC and channel is assigned. Review whether "
                    "the function is intentionally unused or a connection is missing. This "
                    "evidence does not establish SPI use or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "spi_data_family": (family,),
                    "spi_channel": (pin.channel,),
                },
            )
        )
    for pin in unconnected_serial_function_pins(observed):
        role = pin.role.upper()
        found.append(
            Candidate(
                rule_id="bus.serial_unconnected_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This UART/USART {role} function pin has no net assignment while another "
                    "pin in the same component/channel is assigned. Review whether the channel "
                    "is intentionally one-way or a connection is missing. This evidence does "
                    "not establish UART use or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "serial_role": (role,),
                    "serial_channel": (pin.channel,),
                },
            )
        )
    return tuple(found)
