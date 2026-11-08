"""Typed source observations for generic connector I2C review."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_contact_evidence import ConnectorContactEvidence


@dataclass(frozen=True, slots=True)
class I2cGenericEndpointPair:
    """One fitted IC with an exact native SDA/SCL pin pair."""

    reference: str
    sda_pin: str
    sda_net: str
    scl_pin: str
    scl_net: str


@dataclass(frozen=True, slots=True)
class I2cGenericConnectorPair:
    """Generic connector contacts assigned to one recognized I2C bus pair."""

    connector_reference: str
    connector_pin_count: int
    sda_connector_pins: tuple[str, ...]
    sda_connector_functions: tuple[str, ...]
    sda_net: str
    scl_connector_pins: tuple[str, ...]
    scl_connector_functions: tuple[str, ...]
    scl_net: str
    endpoint_pairs: tuple[I2cGenericEndpointPair, ...]
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
