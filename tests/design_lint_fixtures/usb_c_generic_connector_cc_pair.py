"""Synthetic generic connector and USB-C controller CC assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def generic_usb_c_connector_cc_pair_netlist(
    *,
    include_cc2_contact: bool = True,
    connector_functions: tuple[str, str, str] = ("Pin_1", "Pin_2", "GND"),
    controller_functions: tuple[str, str] = ("CC1", "CC2"),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Return a complete native-like source projection for focused regressions."""
    cc2_connector_pins = ("J1.2",) if include_cc2_contact else ()
    nets = {
        "USB_CC1": ("J1.1", "U1.1"),
        "USB_CC2": (*cc2_connector_pins, "U1.2"),
        "USB_GND": ("J1.4", "U1.3"),
    }
    if not include_cc2_contact:
        nets["USB_OTHER"] = ("J1.2",)
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Generic-3-pin"
            ),
            "U1": ComponentContract(value="Synthetic CC controller", footprint="Synthetic:QFN"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "J1": "Synthetic:GenericConnector",
            "U1": "Synthetic:UsbCController",
        },
        pin_functions={
            "J1.1": connector_functions[0],
            "J1.2": connector_functions[1],
            "J1.4": connector_functions[2],
            "U1.1": controller_functions[0],
            "U1.2": controller_functions[1],
            "U1.3": "VSS",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
        },
        component_pin_numbers={"J1": ("1", "2", "4"), "U1": ("1", "2", "3")},
    )
