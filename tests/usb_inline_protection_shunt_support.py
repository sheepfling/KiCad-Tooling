"""Synthetic authored USB inline-path and ESD-shunt combinations."""

from __future__ import annotations

from kicad_tooling.ci_hosted_usb_composite_protection_requirements import (
    composite_inline_protection_map as build_composite_inline_protection_map,
)
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathMap,
)
from tests.usb_data_path_support import usb_inline_component_map, usb_inline_component_netlist


def inline_protection_shunt_map() -> UsbDataPathMap:
    """Map one exact inline data path plus a shunt attached on both path sides."""
    shunt = UsbDataPathProtectionShuntRequirement(
        reference="U6",
        expected_symbol="Synthetic:UsbProtectionArray",
        expected_footprint="Synthetic:DFN-6",
        data_pins=(
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.1", line="D+", net="USB_DP_PORT"),
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.3", line="D-", net="USB_DM_PHY"),
        ),
        pins=(
            UsbDataPathInlinePinRequirement(pin="U6.1", disposition="net", net="USB_DP_PORT"),
            UsbDataPathInlinePinRequirement(pin="U6.2", disposition="net", net="GND"),
            UsbDataPathInlinePinRequirement(pin="U6.3", disposition="net", net="USB_DM_PHY"),
            UsbDataPathInlinePinRequirement(pin="U6.4", disposition="net", net="GND"),
            UsbDataPathInlinePinRequirement(pin="U6.5", disposition="net", net="GND"),
            UsbDataPathInlinePinRequirement(pin="U6.6", disposition="unconnected"),
        ),
    )
    path_map = usb_inline_component_map()
    interface = UsbDataInterfaceRequirement.model_validate(
        {**path_map.interfaces[0].model_dump(), "protection_shunts": (shunt,)}
    )
    return UsbDataPathMap.model_validate({**path_map.model_dump(), "interfaces": (interface,)})


def composite_inline_protection_test_map() -> UsbDataPathMap:
    """Build the shared exact composite map for synthetic interface regressions."""
    return build_composite_inline_protection_map(usb_inline_component_map())


def inline_protection_shunt_netlist(*, wrong_dminus_side: bool = False) -> NetlistContract:
    """Extend the six-pin inline-path contract with one complete protection array."""
    observed = usb_inline_component_netlist()
    components = {
        **observed.components,
        "U6": ComponentContract(
            value="Synthetic USB protection array", footprint="Synthetic:DFN-6"
        ),
    }
    component_symbols = {
        **observed.component_symbols,
        "U6": "Synthetic:UsbProtectionArray",
    }
    component_pin_numbers = {
        **observed.component_pin_numbers,
        "U6": ("1", "2", "3", "4", "5", "6"),
    }
    nets = dict(observed.nets)
    nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "U6.1")
    dminus_net = "USB_DM_PORT" if wrong_dminus_side else "USB_DM_PHY"
    nets[dminus_net] = (*nets[dminus_net], "U6.3")
    nets["GND"] = (*nets["GND"], "U6.2", "U6.4", "U6.5")
    return observed.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "nets": nets,
            "unconnected_nets": {
                **observed.unconnected_nets,
                "NC": (*observed.unconnected_nets.get("NC", ()), "U6.6"),
            },
        }
    )
