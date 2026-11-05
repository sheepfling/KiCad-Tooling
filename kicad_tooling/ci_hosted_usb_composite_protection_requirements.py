"""Synthetic USB maps for a component with inline and protection roles."""

from __future__ import annotations

from .hwrepo.usb_data_path_component_models import (
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from .hwrepo.usb_data_path_models import UsbDataInterfaceRequirement, UsbDataPathMap


def composite_inline_protection_map(base_map: UsbDataPathMap) -> UsbDataPathMap:
    """Add a full two-line protection map for the base map's inline component."""
    if len(base_map.interfaces) != 1:
        raise ValueError("Composite USB fixture maps need exactly one interface")
    interface = base_map.interfaces[0]
    inline = interface.inline_component
    if inline is None:
        raise ValueError("Composite USB protection maps need an exact inline component")

    shunt = UsbDataPathProtectionShuntRequirement(
        reference=inline.reference,
        expected_symbol=inline.expected_symbol,
        expected_footprint=inline.expected_footprint,
        data_pins=(
            UsbDataPathProtectionShuntDataPinRequirement(
                pin=inline.positive_connector_pin,
                line="D+",
                net=interface.positive.connector_net,
            ),
            UsbDataPathProtectionShuntDataPinRequirement(
                pin=inline.positive_phy_pin,
                line="D+",
                net=interface.positive.phy_net,
            ),
            UsbDataPathProtectionShuntDataPinRequirement(
                pin=inline.negative_connector_pin,
                line="D-",
                net=interface.negative.connector_net,
            ),
            UsbDataPathProtectionShuntDataPinRequirement(
                pin=inline.negative_phy_pin,
                line="D-",
                net=interface.negative.phy_net,
            ),
        ),
        pins=inline.pins,
    )
    composite = UsbDataInterfaceRequirement.model_validate(
        {**interface.model_dump(), "protection_shunts": (shunt,)}
    )
    return UsbDataPathMap.model_validate({**base_map.model_dump(), "interfaces": (composite,)})
