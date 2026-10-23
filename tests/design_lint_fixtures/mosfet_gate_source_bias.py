"""Synthetic native-netlist inputs for MOSFET gate-source bias review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def netlist(
    *,
    resistor_value: str | None = None,
    resistor_nets: tuple[str, str] = ("GATE", "SOURCE"),
    dnp: tuple[str, ...] = (),
    symbol: str = "Transistor_FET:Q_NMOS_GDS",
    inventory: tuple[str, ...] = ("1", "2", "3"),
    gate_function: str = "G",
    source_function: str = "S",
    gate_net_members: tuple[str, ...] = ("U1.1",),
) -> NetlistContract:
    """Build a driven supported MOSFET with optional visible source bias."""
    components = {
        "Q1": ComponentContract(value="Synthetic NMOS", footprint="Synthetic:TO-220"),
        "U1": ComponentContract(value="Synthetic output", footprint="Synthetic:Driver"),
    }
    symbols = {"Q1": symbol, "U1": "Synthetic:Driver_OUT"}
    pin_numbers = {"Q1": inventory, "U1": ("1",)}
    pin_functions = {"Q1.1": "D", "Q1.2": gate_function, "Q1.3": source_function, "U1.1": "OUT"}
    nets: dict[str, tuple[str, ...]] = {
        "GATE": ("Q1.2", *gate_net_members),
        "SOURCE": ("Q1.3",),
        "DRAIN": ("Q1.1",),
    }
    if resistor_value is not None:
        components["R1"] = ComponentContract(value=resistor_value, footprint="Synthetic:R_0603")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        pin_functions.update({"R1.1": "Passive", "R1.2": "Passive"})
        for pin, net in zip(("R1.1", "R1.2"), resistor_nets, strict=True):
            nets[net] = (*nets.get(net, ()), pin)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions=pin_functions,
    )
