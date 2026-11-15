"""Synthetic contracts for I2C SDA/SCL resistor-bridge review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i2c_sda_scl_resistive_bridge_netlist(
    *,
    bridge: str = "resistor",
    value: str = "90R",
    resistor_dnp: bool = False,
) -> NetlistContract:
    """Build an I2C pair with a direct bridge or a deliberate control shape."""
    components = {
        "U1": ComponentContract(value="Synthetic I2C controller", footprint="Synthetic:QFN")
    }
    component_symbols = {"U1": "Synthetic:I2cController"}
    component_pin_numbers: dict[str, tuple[str, ...]] = {"U1": ("1", "2")}
    pin_functions = {"U1.1": "SDA", "U1.2": "SCL"}
    dnp_components: tuple[str, ...] = ()

    if bridge == "resistor":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {"I2C_SDA": ("U1.1", "R1.1"), "I2C_SCL": ("U1.2", "R1.2")}
        if resistor_dnp:
            dnp_components = ("R1",)
    elif bridge == "other-net":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "I2C_SDA": ("U1.1",),
            "I2C_SCL": ("U1.2",),
            "AUX_A": ("R1.1",),
            "AUX_B": ("R1.2",),
        }
    elif bridge == "capacitor":
        components["C1"] = ComponentContract(value="100nF", footprint="Synthetic:0603")
        component_symbols["C1"] = "Device:C"
        component_pin_numbers["C1"] = ("1", "2")
        pin_functions.update({"C1.1": "1", "C1.2": "2"})
        nets = {"I2C_SDA": ("U1.1", "C1.1"), "I2C_SCL": ("U1.2", "C1.2")}
    elif bridge == "series":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "I2C_SDA_PHY": ("U1.1", "R1.1"),
            "I2C_SDA_PORT": ("R1.2",),
            "I2C_SCL": ("U1.2",),
        }
    elif bridge == "none":
        nets = {"I2C_SDA": ("U1.1",), "I2C_SCL": ("U1.2",)}
    else:
        raise ValueError(f"Unsupported synthetic I2C bridge shape: {bridge}")

    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        component_pin_numbers=component_pin_numbers,
        pin_electrical_types={"U1.1": "bidirectional", "U1.2": "bidirectional"},
        dnp_components=dnp_components,
    )
