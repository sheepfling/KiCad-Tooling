"""Typed observations for generic connector contacts on a native JTAG pair."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JtagDebugEndpoint:
    """One fitted IC exposing unique TCK and TMS roles on distinct nets."""

    reference: str
    tck_pin: str
    tck_function: str
    tck_electrical_type: str
    tck_net: str
    tms_pin: str
    tms_function: str
    tms_electrical_type: str
    tms_net: str


@dataclass(frozen=True, slots=True)
class JtagGenericConnector:
    """Generic connector contacts assigned to both exact native JTAG nets."""

    connector_reference: str
    connector_pin_count: int
    tck_connector_pins: tuple[str, ...]
    tck_connector_functions: tuple[str, ...]
    tck_net: str
    tms_connector_pins: tuple[str, ...]
    tms_connector_functions: tuple[str, ...]
    tms_net: str
    endpoints: tuple[JtagDebugEndpoint, ...]
