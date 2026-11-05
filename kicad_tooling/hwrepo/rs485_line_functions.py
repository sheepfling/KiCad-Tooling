"""Recognize bounded RS-485 bus-line pin function names."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

_BUS_LINE_ROLES: Mapping[str, Literal["a", "b"]] = MappingProxyType({"a": "a", "b": "b"})
_BUS_LINE_LABEL_ROLES: Mapping[str, Literal["a", "b"]] = MappingProxyType(
    {
        "rs485a": "a",
        "rs485linea": "a",
        "rs485b": "b",
        "rs485lineb": "b",
    }
)


def rs485_bus_line_role(function: str) -> Literal["a", "b"] | None:
    """Return a bus-line role for exact A/B pin functions only."""
    return _BUS_LINE_ROLES.get(function.strip().casefold())


def rs485_bus_line_label_role(net: str) -> Literal["a", "b"] | None:
    """Return a role for exact, unindexed RS-485 A/B net-label aliases."""
    normalized = re.sub(r"[^a-z0-9]", "", net.casefold())
    return _BUS_LINE_LABEL_ROLES.get(normalized)
