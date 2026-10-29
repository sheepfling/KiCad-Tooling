"""Translate unconnected protocol-pin observations."""

from __future__ import annotations

from .bus_signal_roles import unconnected_interface_pins
from .can_unconnected_direction_pins import unconnected_can_direction_pins
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .i2c_unconnected_pins import unconnected_i2c_signal_pins
from .models import NetlistContract
from .rs485_unconnected_line_pin import rs485_unconnected_line_pin_candidates
from .serial_unconnected_pins import unconnected_serial_function_pins
from .spi_unconnected_clock_pin import unconnected_spi_clock_function_pins
from .spi_unconnected_data_pins import unconnected_spi_data_function_pins
from .usb_c_sbu_unconnected_pin import usb_c_sbu_unconnected_pin_candidates
from .usb_unconnected_data import unconnected_usb_data_pins


def unconnected_interface_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Build review prompts for unconnected protocol pins."""
    found: list[Candidate] = []
    for pin in unconnected_i2c_signal_pins(observed):
        found.append(
            Candidate(
                rule_id="bus.i2c_unconnected_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This I2C {pin.role} function pin is unassigned while its paired SDA/SCL "
                    f"pin {pin.paired_pin} is assigned to {pin.paired_net}. Review whether "
                    "the interface is intentionally partial or a connection is missing. The "
                    "function names do not establish bus intent or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "i2c_role": (pin.role,),
                    "paired_pin": (pin.paired_pin,),
                    "paired_net": (pin.paired_net,),
                },
            )
        )
    for pin in unconnected_can_direction_pins(observed):
        role = pin.role.upper()
        paired_role = "RX" if role == "TX" else "TX"
        found.append(
            Candidate(
                rule_id="bus.can_unconnected_direction_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This CAN/FDCAN {role} function pin has no net assignment while its "
                    f"paired {paired_role} pin {pin.paired_pin} is assigned to "
                    f"{pin.paired_net}. Review whether this channel is intentionally "
                    "one-way or a connection is missing. Pin functions do not establish "
                    "channel use or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "can_role": (role,),
                    "can_channel": (pin.channel,),
                    "paired_pin": (pin.paired_pin,),
                    "paired_net": (pin.paired_net,),
                },
            )
        )
    for pin in unconnected_interface_pins(observed):
        if pin.protocol == "spi":
            rule_id: DesignLintRuleId = "bus.spi_unconnected_chip_select"
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
        paired_side = "D−" if pin.side == "positive" else "D+"
        port = f" port {pin.port_index}" if pin.port_index is not None else ""
        found.append(
            Candidate(
                rule_id="bus.usb_unconnected_data_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This native USB 2.0 {side}{port} data pin has no net assignment while its "
                    f"paired {paired_side} pin {pin.paired_pin} is assigned to {pin.paired_net}. "
                    "Review whether the interface is intentionally partial or a connection is "
                    "missing. The pin functions do not establish bus membership or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "USB_data_side": (side,),
                    "paired_pin": (pin.paired_pin,),
                    "paired_function": (pin.paired_function,),
                    "paired_net": (pin.paired_net,),
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
    for pin in unconnected_spi_clock_function_pins(observed):
        found.append(
            Candidate(
                rule_id="bus.spi_unconnected_clock_pin",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    "This native SPI clock-function pin has no net assignment while another "
                    "recognized pin on the same fitted IC and channel is assigned. Review "
                    "whether the clock is intentionally unused or a connection is missing. "
                    "This evidence does not establish SPI use or PCB routing."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "spi_channel": (pin.channel,),
                    "active_peer_pins": pin.active_peer_pins,
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
    found.extend(rs485_unconnected_line_pin_candidates(observed))
    found.extend(usb_c_sbu_unconnected_pin_candidates(observed))
    return tuple(found)
