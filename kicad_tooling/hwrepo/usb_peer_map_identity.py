"""Match authored USB data maps to native connector/PHY endpoint groups."""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from .usb_data_path_models import UsbDataInterfaceRequirement, UsbDataPathMap
from .usb_peer_reference_types import UsbPeerReferencePathCoverage


def usb_data_interface_matches_endpoint_group(
    interface: UsbDataInterfaceRequirement,
    *,
    connector_reference: str,
    phy_reference: str,
    port_groups: AbstractSet[str | None],
) -> bool:
    """Match the project map's endpoint identity, including its optional port scope."""
    return (
        interface.connector_reference.casefold() == connector_reference.casefold()
        and interface.phy_reference.casefold() == phy_reference.casefold()
        and (interface.data_port_group is None or interface.data_port_group in port_groups)
    )


def usb_data_path_map_matches_peer_path(
    path_map: UsbDataPathMap | None,
    path: UsbPeerReferencePathCoverage,
) -> bool:
    """Return whether an authored map owns the observed connector/PHY port group."""
    if path_map is None:
        return False
    return any(
        usb_data_interface_matches_endpoint_group(
            interface,
            connector_reference=path.connector_reference,
            phy_reference=path.phy_reference,
            port_groups={path.data_link.port_group},
        )
        for interface in path_map.interfaces
    )
