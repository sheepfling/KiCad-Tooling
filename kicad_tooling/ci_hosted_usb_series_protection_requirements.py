"""Exact maps for USB series-resistor paths with protection-shunt taps."""

from __future__ import annotations

from kicad_tooling.hwrepo.usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement


def usb_series_protection_shunt_requirements(
    series_map: UsbDataPathMap,
) -> dict[str, UsbDataPathMap]:
    """Extend a synthetic one-resistor-per-line map with exact shunt pin maps."""
    interface = series_map.interfaces[0]

    def mapped_shunt(reference_net: str) -> UsbDataPathProtectionShuntRequirement:
        return UsbDataPathProtectionShuntRequirement(
            reference="U6",
            expected_symbol="Synthetic:UsbProtectionArray",
            expected_footprint="Synthetic:DFN-6",
            data_pins=(
                UsbDataPathProtectionShuntDataPinRequirement(pin="U6.1", line="D+", net="USB_D+"),
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin="U6.3", line="D-", net="USB_DM_PHY"
                ),
            ),
            pins=(
                UsbDataPathInlinePinRequirement(pin="U6.1", disposition="net", net="USB_D+"),
                UsbDataPathInlinePinRequirement(pin="U6.2", disposition="net", net=reference_net),
                UsbDataPathInlinePinRequirement(pin="U6.3", disposition="net", net="USB_DM_PHY"),
                UsbDataPathInlinePinRequirement(pin="U6.4", disposition="net", net=reference_net),
                UsbDataPathInlinePinRequirement(pin="U6.5", disposition="net", net=reference_net),
                UsbDataPathInlinePinRequirement(pin="U6.6", disposition="unconnected"),
            ),
        )

    def with_shunt(*, reference_net: str, common_reference: bool) -> UsbDataPathMap:
        updated = interface.model_copy(
            update={
                "protection_shunts": (mapped_shunt(reference_net),),
                "connector_reference_pins": (
                    (UsbReferencePinRequirement(pin="J1.4", net=reference_net),)
                    if common_reference
                    else ()
                ),
                "phy_reference_pins": (
                    (UsbReferencePinRequirement(pin="U1.3", net=reference_net),)
                    if common_reference
                    else ()
                ),
                "reference_policy": "common_net" if common_reference else None,
            }
        )
        return UsbDataPathMap.model_validate(
            {**series_map.model_dump(), "interfaces": (updated.model_dump(),)}
        )

    return {
        "series-protection-shunt-split-reference": with_shunt(
            reference_net="USB_GND", common_reference=False
        ),
        "series-protection-shunt-common-reference": with_shunt(
            reference_net="GND", common_reference=True
        ),
        "series-protection-shunt-pin-fault": with_shunt(
            reference_net="USB_GND", common_reference=False
        ),
    }
