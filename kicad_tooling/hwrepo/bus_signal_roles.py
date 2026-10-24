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
_I3C_FUNCTION = re.compile(r"(?<![a-z0-9])i3c(?P<channel>\d*)[_\s-]*(?P<role>sda|scl)(?![a-z0-9])")
_I3C_ROLES: dict[str, Literal["SDA", "SCL"]] = {"sda": "SDA", "scl": "SCL"}

_CAN_FUNCTIONS = {
    "canh": "CANH",
    "canhigh": "CANH",
    "canl": "CANL",
    "canlow": "CANL",
}

_USB_C_CC_FUNCTIONS = {"cc1": "CC1", "cc2": "CC2"}
_USB_C_SBU_FUNCTIONS = {"sbu1": "SBU1", "sbu2": "SBU2"}

_SPI_CHIP_SELECT_FUNCTIONS = frozenset(
    {"cs", "csn", "ncs", "nss", "ss", "ssn", "chipselect", "chipselectn"}
)

_SPI_ACTIVE_LOW_CHIP_SELECT_FUNCTIONS = frozenset({"csn", "ncs", "nss", "ssn", "chipselectn"})


@dataclass(frozen=True)
class UnconnectedInterfacePin:
    protocol: Literal["spi", "usb_c", "can"]
    pin: str
    function: str


@dataclass(frozen=True)
class I3cSignalIdentity:
    """One unambiguous I3C SDA or SCL function and its optional channel."""

    channel: str | None
    role: Literal["SDA", "SCL"]


def i2c_signal_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _I2C_FUNCTIONS.get(compact)


def i3c_signal_identity(function: str) -> I3cSignalIdentity | None:
    """Recognize one explicit, optionally channel-indexed I3C SDA/SCL token."""
    matches = tuple(_I3C_FUNCTION.finditer(function.casefold()))
    if len(matches) != 1:
        return None
    match = matches[0]
    channel_text = match.group("channel")
    return I3cSignalIdentity(
        channel=channel_text or None,
        role=_I3C_ROLES[match.group("role")],
    )


def can_function_role(function: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _CAN_FUNCTIONS.get(compact)


def usb_c_cc_role(function: str) -> str | None:
    """Return the bounded USB-C CC1/CC2 function role, if recognized."""
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _USB_C_CC_FUNCTIONS.get(compact)


def usb_c_sbu_role(function: str) -> str | None:
    """Return a bounded USB-C SBU1/SBU2 function role, if recognized."""
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _USB_C_SBU_FUNCTIONS.get(compact)


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
        if compact in _SPI_CHIP_SELECT_FUNCTIONS:
            protocol: Literal["spi", "usb_c", "can"] = "spi"
        elif usb_c_cc_role(function) is not None:
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
