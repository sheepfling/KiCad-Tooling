"""Synthetic BJT base-bias fault and control netlists."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def bjt_base_bias_netlist(
    *,
    family: str = "npn",
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    bias_value: str | None = None,
    bias_nets: tuple[str, str] = ("BASE", "EMITTER"),
    direct_output: bool = False,
    series_resistor_value: str = "1k",
    dnp: tuple[str, ...] = (),
    inventory: tuple[str, ...] | None = None,
    function_overrides: Mapping[str, str] | None = None,
    duplicate_base_assignment: bool = False,
    base_peer: bool = True,
) -> NetlistContract:
    """Build one exact basic BJT with a driven or unsupported base topology."""
    if family not in {"npn", "pnp"}:
        raise ValueError("family must be npn or pnp")
    pins = dict(pin_numbers or {"base": "1", "collector": "2", "emitter": "3"})
    if set(pins) != {"base", "collector", "emitter"}:
        raise ValueError("pin_numbers must map base, collector, and emitter")
    symbol = symbol or f"Transistor_BJT:Q_{family.upper()}_BCE"
    if inventory is None:
        inventory = tuple(pins.values())
    functions = {
        f"Q1.{pins['base']}": "B",
        f"Q1.{pins['collector']}": "C",
        f"Q1.{pins['emitter']}": "E",
        "U1.1": "OUT",
    }
    functions.update(function_overrides or {})

    components = {
        "Q1": ComponentContract(value=f"Synthetic {family.upper()}", footprint="Synthetic:TO-92"),
        "U1": ComponentContract(value="Synthetic output", footprint="Synthetic:Driver"),
    }
    symbols = {"Q1": symbol, "U1": "Synthetic:Drive_OUT"}
    pin_inventories = {"Q1": inventory, "U1": ("1",)}
    nets: dict[str, tuple[str, ...]] = {
        "DRIVE": (),
        "BASE": (f"Q1.{pins['base']}",),
        "EMITTER": (f"Q1.{pins['emitter']}",),
        "COLLECTOR": (f"Q1.{pins['collector']}",),
    }
    if direct_output:
        nets["BASE"] = (*nets["BASE"], "U1.1")
        nets["DRIVE"] = ()
    elif base_peer:
        components["R1"] = ComponentContract(
            value=series_resistor_value,
            footprint="Synthetic:R_0603",
        )
        symbols["R1"] = "Device:R"
        pin_inventories["R1"] = ("1", "2")
        functions.update({"R1.1": "Passive", "R1.2": "Passive"})
        nets["DRIVE"] = ("U1.1", "R1.1")
        nets["BASE"] = (*nets["BASE"], "R1.2")
    else:
        nets["DRIVE"] = ("U1.1",)

    if duplicate_base_assignment:
        nets["BASE_ALT"] = (f"Q1.{pins['base']}",)
    if bias_value is not None:
        components["R2"] = ComponentContract(value=bias_value, footprint="Synthetic:R_0603")
        symbols["R2"] = "Device:R"
        pin_inventories["R2"] = ("1", "2")
        functions.update({"R2.1": "Passive", "R2.2": "Passive"})
        for pin, net in zip(("R2.1", "R2.2"), bias_nets, strict=True):
            nets[net] = (*nets.get(net, ()), pin)

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_inventories,
        pin_functions=functions,
        pin_electrical_types={"U1.1": "output"},
    )
