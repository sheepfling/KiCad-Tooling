"""Synthetic USB peer-reference cases through an exactly mapped inline device."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataPathMap,
    UsbReferencePinRequirement,
)
from tests.usb_data_path_support import (
    usb_inline_component_map,
    usb_inline_component_netlist,
)


def usb_inline_peer_case(
    *,
    reference_policy: Literal["common_net", "separate_nets"] | None = None,
    extra_data_peer: bool = False,
    data_shunt: bool = False,
    inline_has_usb_names: bool = False,
) -> tuple[NetlistContract, UsbDataPathMap]:
    """Build one exact mapped inline path with either common or split references."""
    split = reference_policy != "common_net"
    connector_net = "USB_GND" if split else "GND"
    phy_net = "BOARD_GND" if split else "GND"
    interface = usb_inline_component_map().interfaces[0]
    inline = interface.inline_component
    assert inline is not None
    inline_pins = tuple(
        item.model_copy(update={"net": phy_net}) if item.pin.casefold() == "u2.5" else item
        for item in inline.pins
    )
    inline = inline.model_copy(update={"pins": inline_pins})
    connector_pins = (
        ()
        if reference_policy is None
        else (UsbReferencePinRequirement(pin="J1.4", net=connector_net),)
    )
    phy_pins = (
        () if reference_policy is None else (UsbReferencePinRequirement(pin="U1.3", net=phy_net),)
    )
    interface = interface.model_copy(
        update={
            "inline_component": inline,
            "connector_reference_pins": connector_pins,
            "phy_reference_pins": phy_pins,
            "reference_policy": reference_policy,
        }
    )
    path_map = UsbDataPathMap(
        basis="Synthetic exact USB inline path and optional reference disposition",
        interfaces=(interface,),
    )
    observed = usb_inline_component_netlist()
    nets = dict(observed.nets)
    if split:
        nets.pop("GND")
        nets[connector_net] = ("J1.4",)
        nets[phy_net] = ("U1.3", "U2.5")
    else:
        nets["GND"] = ("J1.4", "U1.3", "U2.5")
    if extra_data_peer:
        nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "TP1.1")
    components = dict(observed.components)
    symbols = dict(observed.component_symbols)
    pin_numbers = dict(observed.component_pin_numbers)
    functions = dict(observed.pin_functions)
    electrical_types = dict(observed.pin_electrical_types)
    if inline_has_usb_names:
        functions.update(
            {
                "U2.1": "D+",
                "U2.2": "DP1",
                "U2.3": "D-",
                "U2.4": "DM1",
                "U2.5": "GND",
                "U2.6": "AUX",
            }
        )
        electrical_types.update(
            {
                "U2.1": "bidirectional",
                "U2.2": "input",
                "U2.3": "bidirectional",
                "U2.4": "input",
                "U2.5": "power_in",
                "U2.6": "passive",
            }
        )
    if data_shunt:
        components["D1"] = ComponentContract(value="Synthetic USB TVS", footprint="Synthetic:SOD")
        symbols["D1"] = "Synthetic:TVS"
        pin_numbers["D1"] = ("1", "2")
        functions.update({"D1.1": "~", "D1.2": "~"})
        electrical_types.update({"D1.1": "passive", "D1.2": "passive"})
        nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "D1.2")
        nets[connector_net] = (*nets[connector_net], "D1.1")
    observed = observed.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
        }
    )
    return observed, path_map
