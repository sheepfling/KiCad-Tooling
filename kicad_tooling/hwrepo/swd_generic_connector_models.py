"""Typed observations for generic connector contacts on an SWD pair."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SwdDebugEndpoint:
    """One fitted IC with a unique native SWDIO/SWCLK pair."""

    reference: str
    swdio_pin: str
    swdio_function: str
    swdio_electrical_type: str
    swdio_net: str
    swclk_pin: str
    swclk_function: str
    swclk_electrical_type: str
    swclk_net: str


@dataclass(frozen=True, slots=True)
class SwdGenericConnector:
    """Generic connector contacts on both exact native SWD nets."""

    connector_reference: str
    connector_pin_count: int
    swdio_connector_pins: tuple[str, ...]
    swdio_connector_functions: tuple[str, ...]
    swdio_net: str
    swclk_connector_pins: tuple[str, ...]
    swclk_connector_functions: tuple[str, ...]
    swclk_net: str
    endpoints: tuple[SwdDebugEndpoint, ...]
