"""Synthetic contracts for I2C SDA/SCL resistor-bridge review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i2c_sda_scl_resistive_bridge_netlist(
    *,
    bridge: str = "resistor",
    value: str = "90R",
    resistor_dnp: bool = False,
    endpoint: str = "ic",
    endpoint_dnp: bool = False,
) -> NetlistContract:
    """Build an IC or connector I2C pair with a bridge or deliberate control."""
    if endpoint not in {"ic", "connector"}:
        raise ValueError(f"Unsupported synthetic I2C endpoint: {endpoint}")
    endpoint_reference = "U1" if endpoint == "ic" else "J1"
    endpoint_symbol = (
        "Synthetic:I2cController" if endpoint == "ic" else "Connector_Generic:Conn_01x02"
    )
    endpoint_type = "bidirectional" if endpoint == "ic" else "passive"
    components = {
        endpoint_reference: ComponentContract(
            value="Synthetic I2C controller" if endpoint == "ic" else "Synthetic I2C connector",
            footprint="Synthetic:QFN" if endpoint == "ic" else "Synthetic:Conn_01x02",
        )
    }
    component_symbols = {endpoint_reference: endpoint_symbol}
    component_pin_numbers: dict[str, tuple[str, ...]] = {endpoint_reference: ("1", "2")}
    pin_functions = {f"{endpoint_reference}.1": "SDA", f"{endpoint_reference}.2": "SCL"}
    dnp_components: tuple[str, ...] = ()

    if bridge == "resistor":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "I2C_SDA": (f"{endpoint_reference}.1", "R1.1"),
            "I2C_SCL": (f"{endpoint_reference}.2", "R1.2"),
        }
        if resistor_dnp:
            dnp_components = ("R1",)
    elif bridge == "other-net":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "I2C_SDA": (f"{endpoint_reference}.1",),
            "I2C_SCL": (f"{endpoint_reference}.2",),
            "AUX_A": ("R1.1",),
            "AUX_B": ("R1.2",),
        }
    elif bridge == "capacitor":
        components["C1"] = ComponentContract(value="100nF", footprint="Synthetic:0603")
        component_symbols["C1"] = "Device:C"
        component_pin_numbers["C1"] = ("1", "2")
        pin_functions.update({"C1.1": "1", "C1.2": "2"})
        nets = {
            "I2C_SDA": (f"{endpoint_reference}.1", "C1.1"),
            "I2C_SCL": (f"{endpoint_reference}.2", "C1.2"),
        }
    elif bridge == "series":
        components["R1"] = ComponentContract(value=value, footprint="Synthetic:0603")
        component_symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets = {
            "I2C_SDA_PHY": (f"{endpoint_reference}.1", "R1.1"),
            "I2C_SDA_PORT": ("R1.2",),
            "I2C_SCL": (f"{endpoint_reference}.2",),
        }
    elif bridge == "none":
        nets = {"I2C_SDA": (f"{endpoint_reference}.1",), "I2C_SCL": (f"{endpoint_reference}.2",)}
    else:
        raise ValueError(f"Unsupported synthetic I2C bridge shape: {bridge}")

    if endpoint_dnp:
        dnp_components = (endpoint_reference,)

    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        component_pin_numbers=component_pin_numbers,
        pin_electrical_types={
            f"{endpoint_reference}.1": endpoint_type,
            f"{endpoint_reference}.2": endpoint_type,
        },
        dnp_components=dnp_components,
    )
