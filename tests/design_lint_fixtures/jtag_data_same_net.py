"""Tooling-owned JTAG TDI/TDO same-net cases for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def jtag_data_same_net_netlist(
    *,
    shared: bool = True,
    dnp: bool = False,
    reference: str = "U1",
    functions: tuple[str, str, str, str] = (
        "JTAG_TCK",
        "JTAG_TMS",
        "JTAG_TDI",
        "JTAG_TDO",
    ),
    pin_types: tuple[str, str] = ("passive", "passive"),
) -> NetlistContract:
    """Build one complete JTAG IC with shared or separate TDI/TDO assignments."""
    pin_numbers = ("1", "2", "3", "4")
    pins = tuple(f"{reference}.{number}" for number in pin_numbers)
    nets = {
        "JTAG_TCK_U1": (pins[0],),
        "JTAG_TMS_U1": (pins[1],),
    }
    if shared:
        nets["JTAG_DATA_SHARED"] = (pins[2], pins[3])
    else:
        nets["JTAG_TDI_U1"] = (pins[2],)
        nets["JTAG_TDO_U1"] = (pins[3],)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic JTAG TAP", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={reference: "Synthetic:JtagDebugTarget"},
        pin_functions=dict(zip(pins, functions, strict=True)),
        pin_electrical_types={
            pins[0]: "passive",
            pins[1]: "passive",
            pins[2]: pin_types[0],
            pins[3]: pin_types[1],
        },
        component_pin_numbers={reference: pin_numbers},
        dnp_components=(reference,) if dnp else (),
    )
