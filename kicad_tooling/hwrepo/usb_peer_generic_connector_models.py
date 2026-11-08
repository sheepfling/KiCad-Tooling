"""Typed observations for USB PHY pairs attached to generic connector pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_contact_evidence import ConnectorContactEvidence


@dataclass(frozen=True, slots=True)
class UsbGenericConnectorDataPair:
    """Native connector-pin assignments matching one recognized USB PHY pair."""

    connector_reference: str
    phy_reference: str
    port_group: str | None
    positive_pins: tuple[str, ...]
    positive_functions: tuple[str, ...]
    positive_net: str
    negative_pins: tuple[str, ...]
    negative_functions: tuple[str, ...]
    negative_net: str
    connector_pin_count: int
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class UsbGenericConnectorSuperspeedPair:
    """Native generic connector contacts on one recognized USB SuperSpeed pair."""

    connector_reference: str
    phy_reference: str
    signal_family: Literal["USB SuperSpeed TX", "USB SuperSpeed RX"]
    phy_positive_pin: str
    positive_pins: tuple[str, ...]
    positive_functions: tuple[str, ...]
    positive_net: str
    negative_pins: tuple[str, ...]
    negative_functions: tuple[str, ...]
    negative_net: str
    phy_negative_pin: str
    connector_pin_count: int
    other_connector_contacts: tuple[ConnectorContactEvidence, ...] = ()
