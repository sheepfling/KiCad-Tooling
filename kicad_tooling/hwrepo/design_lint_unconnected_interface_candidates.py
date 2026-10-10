"""Translate unconnected protocol-pin observations."""

from __future__ import annotations

from .bus_signal_roles import unconnected_interface_pins
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract


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
    return tuple(found)
