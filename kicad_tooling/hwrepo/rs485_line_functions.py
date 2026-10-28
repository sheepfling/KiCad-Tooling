"""Recognize bounded RS-485 bus-line pin function names."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

_BUS_LINE_ROLES: Mapping[str, Literal["a", "b"]] = MappingProxyType({"a": "a", "b": "b"})


def rs485_bus_line_role(function: str) -> Literal["a", "b"] | None:
    """Return a bus-line role for exact A/B pin functions only."""
    return _BUS_LINE_ROLES.get(function.strip().casefold())
