"""Recognize bounded RS-485 transceiver data-pin function aliases."""

from __future__ import annotations

import re
from typing import Literal

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
