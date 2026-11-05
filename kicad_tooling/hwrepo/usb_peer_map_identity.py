"""Match authored USB data maps to native connector/PHY endpoint groups."""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from .usb_data_path_models import UsbDataInterfaceRequirement


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
