"""Choose the bounded USB peer-reference disposition for a supported path."""

from __future__ import annotations

from typing import Literal

from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_contract import usb_reference_map_matches
from .usb_peer_reference_types import UsbEndpoint, UsbPeerDataLink

UsbPeerReferenceDisposition = Literal[
    "COMMON_REFERENCE",
    "SEPARATE_REFERENCE_REVIEW",
    "MAP_COVERED_SEPARATE_REFERENCE",
]


def usb_peer_reference_disposition(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    data_link: UsbPeerDataLink,
    path_map: UsbDataPathMap | None,
) -> UsbPeerReferenceDisposition:
    """Classify whether a supported USB peer path needs a default review prompt."""
    if connector.reference_net.casefold() == phy.reference_net.casefold():
        return "COMMON_REFERENCE"
    if usb_reference_map_matches(connector, phy, data_link, path_map):
        return "MAP_COVERED_SEPARATE_REFERENCE"
    return "SEPARATE_REFERENCE_REVIEW"
