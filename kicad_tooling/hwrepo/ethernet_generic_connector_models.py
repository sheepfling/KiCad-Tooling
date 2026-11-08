"""Typed native observations for generic connector contacts on Ethernet PHY pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_contact_evidence import ConnectorContactEvidence

EthernetPairDirection = Literal["TX", "RX"]


@dataclass(frozen=True, slots=True)
class EthernetGenericEndpointPair:
    """One fitted IC's exact native Ethernet data-pair assignment."""

    reference: str
    direction: EthernetPairDirection
    positive_pin: str
    positive_net: str
    negative_pin: str
    negative_net: str


@dataclass(frozen=True, slots=True)
class EthernetGenericConnectorPair:
    """Generic connector contacts on the exact nets of one Ethernet PHY pair."""

    connector_reference: str
    connector_pin_count: int
    direction: EthernetPairDirection
    positive_connector_pins: tuple[str, ...]
    positive_connector_functions: tuple[str, ...]
    positive_net: str
    negative_connector_pins: tuple[str, ...]
    negative_connector_functions: tuple[str, ...]
    negative_net: str
    endpoint_pairs: tuple[EthernetGenericEndpointPair, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
