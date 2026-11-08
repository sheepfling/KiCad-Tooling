"""Typed native observations for generic CAN connector contacts."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import ConnectorContactEvidence


@dataclass(frozen=True, slots=True)
class CanGenericEndpointPair:
    """One fitted IC's exact native CANH/CANL endpoint pair."""

    reference: str
    canh_pin: str
    canh_net: str
    canl_pin: str
    canl_net: str


@dataclass(frozen=True, slots=True)
class CanGenericConnectorPair:
    """Generic connector contacts assigned to one recognized CAN bus pair."""

    connector_reference: str
    connector_pin_count: int
    canh_connector_pins: tuple[str, ...]
    canh_connector_functions: tuple[str, ...]
    canh_net: str
    canl_connector_pins: tuple[str, ...]
    canl_connector_functions: tuple[str, ...]
    canl_net: str
    endpoint_pairs: tuple[CanGenericEndpointPair, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
