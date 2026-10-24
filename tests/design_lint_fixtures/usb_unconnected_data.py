"""Synthetic USB 2.0 data-pin netlists for open-pin review coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_unconnected_data_netlist(
    *,
    open_pins: tuple[str, ...] = ("J1.1",),
    dnp_components: tuple[str, ...] = (),
    functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build a direct USB 2.0 pair with configurable open endpoint pins."""
    pin_functions = functions or {
        "J1.1": "D+",
        "J1.2": "D-",
        "U1.1": "USB_DP",
        "U1.2": "USB_DM",
    }
    assignments = {
        "USB_D+": ("J1.1", "U1.1"),
        "USB_D-": ("J1.2", "U1.2"),
    }
    open_keys = {pin.casefold() for pin in open_pins}
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in assignments.items()
    }
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB port", footprint="Lint:USB"),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Lint:PHY"),
        },
        nets=nets,
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={"J1": "Synthetic:USB_A", "U1": "Synthetic:UsbPhy"},
        pin_functions=pin_functions,
        component_pin_numbers={"J1": ("1", "2"), "U1": ("1", "2")},
    )
