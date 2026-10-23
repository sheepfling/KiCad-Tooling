"""Small synthetic netlists for the MOSFET direct gate-drive review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def netlist(
    *,
    driver_type: str = "output",
    series_resistor: bool = False,
    driver_also_on_other_net: bool = False,
    dnp: tuple[str, ...] = (),
    symbol: str = "Transistor_FET:Q_NMOS_GDS",
    inventory: tuple[str, ...] = ("1", "2", "3"),
    gate_function: str = "G",
) -> NetlistContract:
    """Build a supported MOSFET with direct or resistor-separated drive."""
    components = {
        "Q1": ComponentContract(value="Synthetic NMOS", footprint="Synthetic:TO-220"),
        "U1": ComponentContract(value="Synthetic driver", footprint="Synthetic:Driver"),
    }
    symbols = {"Q1": symbol, "U1": "Synthetic:Driver_OUT"}
    pin_numbers = {"Q1": inventory, "U1": ("1",)}
    functions = {"Q1.1": "D", "Q1.2": gate_function, "Q1.3": "S", "U1.1": "OUT"}
    electrical_types = {"U1.1": driver_type}
    nets: dict[str, tuple[str, ...]] = {"DRAIN": ("Q1.1",), "SOURCE": ("Q1.3",)}
    if series_resistor:
        components["R1"] = ComponentContract(value="22", footprint="Synthetic:R_0603")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        functions.update({"R1.1": "Passive", "R1.2": "Passive"})
        electrical_types.update({"R1.1": "passive", "R1.2": "passive"})
        nets["DRIVER_OUT"] = ("U1.1", "R1.1")
        nets["GATE"] = ("Q1.2", "R1.2")
    else:
        nets["GATE"] = ("Q1.2", "U1.1")
    if driver_also_on_other_net:
        nets["OTHER"] = ("U1.1",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
    )
