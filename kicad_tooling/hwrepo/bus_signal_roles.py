"""Bus signal roles for deterministic KiCad bus analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import NetlistContract

_I2C_FUNCTIONS = {
    "sda": "SDA",
    "i2csda": "SDA",
    "scl": "SCL",
    "i2cscl": "SCL",
}

_CAN_FUNCTIONS = {
    "canh": "CANH",
    "canhigh": "CANH",
    "canl": "CANL",
    "canlow": "CANL",
}

_SPI_CHIP_SELECT_FUNCTIONS = frozenset(
    {"cs", "csn", "ncs", "nss", "ss", "ssn", "chipselect", "chipselectn"}
)

_SPI_ACTIVE_LOW_CHIP_SELECT_FUNCTIONS = frozenset({"csn", "ncs", "nss", "ssn", "chipselectn"})


@dataclass(frozen=True)
class UnconnectedInterfacePin:
    protocol: Literal["i2c", "spi", "usb_c", "can"]
    pin: str
    function: str


def i2c_signal_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _I2C_FUNCTIONS.get(compact)


def can_function_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _CAN_FUNCTIONS.get(compact)


def unconnected_interface_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedInterfacePin, ...]:
    """Find unassigned pins with a narrow, recognizable interface function."""
    connected = {pin for pins in observed.nets.values() for pin in pins}
    gaps: list[UnconnectedInterfacePin] = []
    for pin, function in observed.pin_functions.items():
        if pin in connected:
            continue
        compact = re.sub(r"[^a-z0-9]", "", function.casefold())
        if i2c_signal_role(function) is not None:
            protocol: Literal["i2c", "spi", "usb_c", "can"] = "i2c"
        elif compact in _SPI_CHIP_SELECT_FUNCTIONS:
            protocol = "spi"
        elif compact in {"cc1", "cc2"}:
            protocol = "usb_c"
        elif can_function_role(function) is not None:
            protocol = "can"
        else:
            continue
        gaps.append(UnconnectedInterfacePin(protocol=protocol, pin=pin, function=function))
    return tuple(sorted(gaps, key=lambda item: (item.protocol, item.pin, item.function)))


def is_active_low_chip_select_function(function: str) -> bool:
    """Recognize explicit active-low spelling without assuming bare CS polarity."""
    raw = function.casefold().replace("−", "-").strip()
    compact = re.sub(r"[^a-z0-9]", "", raw)
    if compact in _SPI_ACTIVE_LOW_CHIP_SELECT_FUNCTIONS:
        return True
    active_low_marked = any(marker in raw for marker in ("~", "#", "!", "/", "̅"))
    return active_low_marked and compact in {"cs", "ss", "chipselect"}
