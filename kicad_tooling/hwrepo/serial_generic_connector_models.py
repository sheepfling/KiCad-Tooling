"""Typed native observations for generic UART connector review."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import ConnectorContactEvidence


@dataclass(frozen=True, slots=True)
class SerialGenericEndpointPair:
    """One fitted IC's exact native UART TX/RX assignments."""

    reference: str
    channel: str
    tx_pin: str
    tx_net: str
    rx_pin: str
    rx_net: str


@dataclass(frozen=True, slots=True)
class SerialGenericConnectorPair:
    """Generic connector contacts assigned to one exact UART TX/RX pair."""

    connector_reference: str
    connector_pin_count: int
    tx_connector_pins: tuple[str, ...]
    tx_connector_functions: tuple[str, ...]
    tx_net: str
    rx_connector_pins: tuple[str, ...]
    rx_connector_functions: tuple[str, ...]
    rx_net: str
    endpoint_pairs: tuple[SerialGenericEndpointPair, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
