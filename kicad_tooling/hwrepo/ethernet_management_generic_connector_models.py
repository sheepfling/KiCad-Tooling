"""Typed observations for Ethernet MDC/MDIO generic-connector review."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import ConnectorContactEvidence


@dataclass(frozen=True, slots=True)
class EthernetManagementEndpoint:
    """One fitted IC's unique MDC and MDIO assignments."""

    reference: str
    mdc_pin: str
    mdc_net: str
    mdio_pin: str
    mdio_net: str


@dataclass(frozen=True, slots=True)
class EthernetManagementGenericConnector:
    """Generic connector contacts on both exact Ethernet-management nets."""

    connector_reference: str
    connector_pin_count: int
    mdc_connector_pins: tuple[str, ...]
    mdc_connector_functions: tuple[str, ...]
    mdc_net: str
    mdio_connector_pins: tuple[str, ...]
    mdio_connector_functions: tuple[str, ...]
    mdio_net: str
    endpoint_pairs: tuple[EthernetManagementEndpoint, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
