"""Compose an exact series-resistor USB path with a complete shunt map."""

from __future__ import annotations

from .hwrepo.usb_data_path_component_models import (
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from .hwrepo.usb_data_path_models import UsbDataPathMap
from .hwrepo.usb_reference_pin_models import UsbReferencePinRequirement


def series_shunt_path_map(
    series_map: UsbDataPathMap,
    protection_shunt: UsbDataPathProtectionShuntRequirement,
) -> UsbDataPathMap:
    """Bind endpoint-side D+/D− taps to a source-reviewed series-resistor map."""
    shunt_nets = {"U6.1": "USB_DP_PORT", "U6.3": "USB_DM_PHY"}
    shunt = UsbDataPathProtectionShuntRequirement.model_validate(
        {
            **protection_shunt.model_dump(),
            "data_pins": (
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin="U6.1", line="D+", net="USB_DP_PORT"
                ),
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin="U6.3", line="D-", net="USB_DM_PHY"
                ),
            ),
            "pins": tuple(
                item.model_copy(update={"net": shunt_nets[item.pin]})
                if item.pin in shunt_nets
                else item
                for item in protection_shunt.pins
            ),
        }
    )
    interface = series_map.interfaces[0]
    combined = interface.model_copy(
        update={
            "positive": interface.positive.model_copy(update={"connector_net": "USB_DP_PORT"}),
            "negative": interface.negative.model_copy(update={"connector_net": "USB_DM_PORT"}),
            "protection_shunts": (shunt,),
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.4", net="BOARD_GND"),),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
            "reference_policy": "common_net",
        }
    )
    return series_map.model_copy(update={"interfaces": (combined,)})
