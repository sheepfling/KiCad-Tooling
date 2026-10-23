"""Synthetic MOSFET main-terminal connectivity for component lint tests."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def mosfet_drain_source_netlist(
    *,
    channel_type: str = "nmos",
    same_net: bool = True,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    function_overrides: Mapping[str, str] | None = None,
    open_roles: tuple[str, ...] = (),
    extra_drain_net: str | None = None,
) -> NetlistContract:
    """Build one exact supported MOSFET with controllable native pin/net cases."""
    if channel_type not in {"nmos", "pmos"}:
        raise ValueError("channel_type must be nmos or pmos")
    numbers = dict(pin_numbers or {"drain": "1", "gate": "2", "source": "3"})
    if set(numbers) != {"drain", "gate", "source"}:
        raise ValueError("pin_numbers must map drain, gate, and source")
    if symbol is None:
        symbol = f"Transistor_FET:Q_{channel_type.upper()}_DGS"

    functions = {
        f"Q1.{numbers['drain']}": "D",
        f"Q1.{numbers['gate']}": "G",
        f"Q1.{numbers['source']}": "S",
        "U1.1": "OUT",
    }
    functions.update(function_overrides or {})
    assignments: dict[str, list[str]] = {}
    drain_net = "SWITCHED" if same_net else "+5V"
    source_net = "SWITCHED" if same_net else "GND"
    role_nets = {
        "drain": drain_net,
        "gate": "GATE_CTRL",
        "source": source_net,
    }
    for role, number in numbers.items():
        if role in open_roles:
            continue
        net = role_nets[role]
        assignments.setdefault(net, []).append(f"Q1.{number}")
    assignments.setdefault("GATE_CTRL", []).append("U1.1")
    if extra_drain_net is not None:
        assignments.setdefault(extra_drain_net, []).append(f"Q1.{numbers['drain']}")

    return NetlistContract(
        components={
            "Q1": ComponentContract(
                value=f"Synthetic {channel_type.upper()}", footprint="Synthetic:TO-220"
            ),
            "U1": ComponentContract(value="Synthetic gate driver", footprint="Synthetic:DIP-8"),
        },
        nets={net: tuple(pins) for net, pins in assignments.items()},
        dnp_components=dnp,
        component_symbols={"Q1": symbol, "U1": "Synthetic:Gate_Driver"},
        component_pin_numbers={"Q1": inventory, "U1": ("1",)},
        pin_functions=functions,
    )
