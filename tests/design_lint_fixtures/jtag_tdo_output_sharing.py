"""Tooling-owned JTAG TDO sharing netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def jtag_tdo_output_sharing_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    functions: tuple[str, ...] | None = None,
    pin_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build complete JTAG endpoints with one shared or separate TDO net."""
    selected_functions = functions or tuple("JTAG_TDO" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets["JTAG_TDO_SHARED"] = tuple(f"{reference}.4" for reference in references)
    for index, reference in enumerate(references):
        pin_numbers = ("1", "2", "3", "4")
        inventory[reference] = pin_numbers
        functions_for_reference = ("JTAG_TCK", "JTAG_TMS", "JTAG_TDI", selected_functions[index])
        for number, function in zip(pin_numbers, functions_for_reference, strict=True):
            pin = f"{reference}.{number}"
            pin_functions[pin] = function
            pin_types[pin] = pin_type if number == "4" else "passive"
            if number == "4" and shared:
                continue
            net = f"JTAG_{function}_{reference}"
            nets[net] = (pin,)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic JTAG TAP", footprint="Synthetic:QFN")
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:JtagDebugTarget" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
