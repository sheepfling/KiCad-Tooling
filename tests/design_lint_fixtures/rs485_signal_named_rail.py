"""Synthetic RS-485 transceiver pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_signal_named_rail_netlist(
    *,
    pin: str = "U1.1",
    rail_name: str = "GND",
    function: str = "D",
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
) -> NetlistContract:
    """Assign one explicit RS-485 D/R role to a rail-like net label."""
    functions = {"U1.1": "D", "U1.2": "R"}
    if pin not in functions:
        raise ValueError(f"Unsupported synthetic RS-485 data pin: {pin}")
    functions[pin] = function
    nets = {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
    nets.pop("HOST_TX" if pin == "U1.1" else "HOST_RX")
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions=functions,
        component_pin_numbers={"U1": ("1", "2")},
    )


def rs485_module_connector_named_rail_netlist(
    *,
    connector_value: str = "MAX485 transceiver module",
    pin_numbers: tuple[str, ...] = ("1", "2"),
    dnp: bool = False,
) -> NetlistContract:
    """Add an identified module connector with DI and RO pins on named rails."""
    base = rs485_signal_named_rail_netlist(rail_name="HOST_TX")
    return base.model_copy(
        update={
            "components": {
                **base.components,
                "J1": base.components["U1"].model_copy(update={"value": connector_value}),
            },
            "component_symbols": {
                **base.component_symbols,
                "J1": "Connector_Generic:Conn_01x02",
            },
            "pin_functions": {**base.pin_functions, "J1.1": "DI", "J1.2": "RO"},
            "component_pin_numbers": {**base.component_pin_numbers, "J1": pin_numbers},
            "dnp_components": ("J1",) if dnp else (),
            "nets": {**base.nets, "GND": ("J1.1",), "+3V3": ("J1.2",)},
        }
    )
