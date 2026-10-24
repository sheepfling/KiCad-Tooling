"""Synthetic USB 2.0 PHY data-pin assignments for same-net review tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_data_same_net_netlist(
    *,
    positive_function: str = "USB D+",
    negative_function: str = "USB D-",
    shared: bool = True,
    dnp: bool = False,
    positive_type: str = "bidirectional",
    negative_type: str = "bidirectional",
) -> NetlistContract:
    """Build a fitted or DNP two-pin USB data endpoint."""
    nets = (
        {"USB_SHARED": ("U1.1", "U1.2")} if shared else {"USB_DP": ("U1.1",), "USB_DM": ("U1.2",)}
    )
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN")},
        nets=nets,
        component_symbols={"U1": "Synthetic:UsbPhy"},
        pin_functions={"U1.1": positive_function, "U1.2": negative_function},
        component_pin_numbers={"U1": ("1", "2")},
        pin_electrical_types={"U1.1": positive_type, "U1.2": negative_type},
        dnp_components=("U1",) if dnp else (),
    )
