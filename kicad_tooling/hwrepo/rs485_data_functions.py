"""Recognize bounded RS-485 transceiver data-pin function aliases."""

from __future__ import annotations

import re
from typing import Literal

from .casefold_mapping_lookup import lookup_unique_casefold
from .models import NetlistContract

_EXPLICIT_RS485_IDENTITY = re.compile(
    r"(?:rs[^a-z0-9]*485|(?:max|adm)[-_ ]?[a-z0-9]*48[0-9]{1,2}|sp[-_ ]?3485|sn65hvd485[a-z0-9]*|thvd[a-z0-9]*)",
    re.IGNORECASE,
)

_DATA_PIN_ROLES: dict[str, Literal["tx", "rx"]] = {
    "d": "tx",
    "di": "tx",
    "driverdatain": "tx",
    "driverinput": "tx",
    "r": "rx",
    "ro": "rx",
    "receiverdataout": "rx",
    "receiveroutput": "rx",
}


def rs485_data_pin_role(function: str) -> Literal["tx", "rx"] | None:
    """Map driver-data input and receiver-data output aliases to host UART roles."""
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _DATA_PIN_ROLES.get(compact)


def is_explicit_rs485_transceiver_identity(identity: str) -> bool:
    """Return whether native identity text contains a bounded RS-485 marker."""
    return _EXPLICIT_RS485_IDENTITY.search(identity) is not None


def explicit_rs485_transceiver_identity(observed: NetlistContract, reference: str) -> str | None:
    """Return identity evidence only when a fitted symbol/value identifies RS-485."""
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    component = lookup_unique_casefold(observed.components, reference)
    if component is None:
        return None
    identity = " ".join(
        value for value in (symbol, component.value) if value
    )
    if not is_explicit_rs485_transceiver_identity(identity):
        return None
    return identity
