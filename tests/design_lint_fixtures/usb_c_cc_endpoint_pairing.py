"""Synthetic USB-C connector/controller CC endpoint assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_cc_endpoint_pairing_netlist(
    *,
    crossed: bool = True,
    dnp: tuple[str, ...] = (),
    duplicate_controller_function: bool = False,
    incomplete_controller_inventory: bool = False,
    ambiguous_connector_assignment: bool = False,
    same_net: bool = False,
) -> NetlistContract:
    """Return a synthetic endpoint pair with a selectable crossed mapping."""
    if same_net:
        nets = {"CC_SHARED": ("J1.1", "J1.2", "U1.1", "U1.2")}
    elif crossed:
        nets = {
            "CC1_BUS": ("J1.1", "U1.2"),
            "CC2_BUS": ("J1.2", "U1.1"),
        }
    else:
        nets = {
            "CC1_BUS": ("J1.1", "U1.1"),
            "CC2_BUS": ("J1.2", "U1.2"),
        }
    if ambiguous_connector_assignment:
        nets["OTHER"] = ("J1.1",)
    functions = {"J1.1": "CC1", "J1.2": "CC2", "U1.1": "CC1", "U1.2": "CC2"}
    inventory = {"J1": ("1", "2"), "U1": ("1", "2")}
    if duplicate_controller_function:
        functions["U1.3"] = "CC1"
        inventory["U1"] = (*inventory["U1"], "3")
    if incomplete_controller_inventory:
        inventory["U1"] = ("1",)
    return NetlistContract(
        components={
            reference: ComponentContract(value=value, footprint="Synthetic:QFN")
            for reference, value in (("J1", "USB-C connector"), ("U1", "USB-C controller"))
        },
        nets=nets,
        component_symbols={"J1": "Connector:USB_C_Receptacle", "U1": "Synthetic:USB_C_Controller"},
        pin_functions=functions,
        component_pin_numbers=inventory,
        dnp_components=dnp,
    )
