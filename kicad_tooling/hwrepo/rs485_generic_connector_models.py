"""Typed observations for generic connector contacts on an RS-485 line pair."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rs485GenericEndpointPair:
    """One fitted, identified transceiver's native A/B line assignments."""

    reference: str
    a_pin: str
    a_net: str
    b_pin: str
    b_net: str


@dataclass(frozen=True, slots=True)
class Rs485GenericConnectorPair:
    """Generic connector contacts assigned to one identified RS-485 A/B pair."""

    connector_reference: str
    connector_pin_count: int
    a_connector_pins: tuple[str, ...]
    a_connector_functions: tuple[str, ...]
    a_net: str
    b_connector_pins: tuple[str, ...]
    b_connector_functions: tuple[str, ...]
    b_net: str
    endpoint_pairs: tuple[Rs485GenericEndpointPair, ...]
