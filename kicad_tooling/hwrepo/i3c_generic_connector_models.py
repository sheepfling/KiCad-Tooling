"""Typed observations for generic connector/I3C pair review."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import ConnectorContactEvidence
from .i3c_endpoint_pairs import I3cEndpointPair


@dataclass(frozen=True, slots=True)
class I3cGenericConnectorPair:
    """Generic connector contacts assigned to one recognized I3C pair."""

    connector_reference: str
    connector_pin_count: int
    sda_connector_pins: tuple[str, ...]
    sda_connector_functions: tuple[str, ...]
    sda_net: str
    scl_connector_pins: tuple[str, ...]
    scl_connector_functions: tuple[str, ...]
    scl_net: str
    endpoint_pairs: tuple[I3cEndpointPair, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
