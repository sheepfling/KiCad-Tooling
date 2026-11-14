"""Synthetic native-netlist shapes for USB data-pair resistor review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_data_pair_bridge_netlist(
    *,
    bridge: str = "resistor",
    value: str = "90R",
    resistor_dnp: bool = False,
) -> NetlistContract:
    """Build a synthetic USB PHY with a direct, absent, or series passive path."""
    components = {"U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN")}
    component_symbols = {"U1": "Synthetic:UsbPhy"}
    component_pin_numbers: dict[str, tuple[str, ...]] = {"U1": ("1", "2")}
    pin_functions = {"U1.1": "USB D+", "U1.2": "USB D-"}
    nets: dict[str, tuple[str, ...]]
    dnp_components: tuple[str, ...] = ()

    if bridge == "resistor":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {"USB_DP": ("U1.1", "R1.1"), "USB_DM": ("U1.2", "R1.2")}
        if resistor_dnp:
            dnp_components = ("R1",)
    elif bridge == "capacitor":
        components["C1"] = ComponentContract(value="100nF", footprint="Synthetic:0603")
        component_symbols["C1"] = "Device:C"
        component_pin_numbers["C1"] = ("1", "2")
        pin_functions.update({"C1.1": "1", "C1.2": "2"})
        nets = {"USB_DP": ("U1.1", "C1.1"), "USB_DM": ("U1.2", "C1.2")}
    elif bridge == "series":
        components["R1"] = ComponentContract(value="27R", footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "USB_DP_PHY": ("U1.1", "R1.2"),
            "USB_DP_PORT": ("R1.1",),
            "USB_DM": ("U1.2",),
        }
    elif bridge == "none":
        nets = {"USB_DP": ("U1.1",), "USB_DM": ("U1.2",)}
    else:
        raise ValueError(f"Unsupported synthetic USB bridge shape: {bridge}")

    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        component_pin_numbers=component_pin_numbers,
        pin_electrical_types={"U1.1": "bidirectional", "U1.2": "bidirectional"},
        dnp_components=dnp_components,
    )
