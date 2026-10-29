"""Synthetic USB-C SBU and controller CC shared-net assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_sbu_same_net_netlist(
    *,
    shared: bool = True,
    dnp: bool = False,
    reference: str = "U1",
    functions: tuple[str, str] = ("SBU1", "SBU2"),
    inventory: tuple[str, ...] = ("1", "2"),
) -> NetlistContract:
    """Build a fitted synthetic controller with shared or distinct SBU lines."""
    first_pin, second_pin = f"{reference}.1", f"{reference}.2"
    nets = (
        {"SBU_SHARED": (first_pin, second_pin)}
        if shared
        else {"SBU1_BUS": (first_pin,), "SBU2_BUS": (second_pin,)}
    )
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic USB-C controller", footprint="Synthetic:QFN"
            )
        },
        nets=nets,
        component_symbols={reference: "Synthetic:USB_C_Controller"},
        pin_functions={first_pin: functions[0], second_pin: functions[1]},
        component_pin_numbers={reference: inventory},
        dnp_components=(reference,) if dnp else (),
    )


def usb_c_cc_controller_same_net_netlist(
    *, shared: bool = True, dnp: bool = False, functions: tuple[str, str] = ("CC1", "CC2")
) -> NetlistContract:
    """Build a synthetic USB-C controller with shared or separate CC pins."""
    nets = (
        {"CC_SHARED": ("U1.1", "U1.2")} if shared else {"CC1_BUS": ("U1.1",), "CC2_BUS": ("U1.2",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic USB-C controller", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:USB_C_Controller"},
        pin_functions={"U1.1": functions[0], "U1.2": functions[1]},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )
