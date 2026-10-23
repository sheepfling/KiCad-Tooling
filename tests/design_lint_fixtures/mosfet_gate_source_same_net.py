"""Synthetic MOSFET gate/source assignments for component lint tests."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def mosfet_gate_source_netlist(
    *,
    same_net: bool = True,
    symbol: str = "Transistor_FET:Q_NMOS_DGS",
    pin_numbers: Mapping[str, str] | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    function_overrides: Mapping[str, str] | None = None,
    open_roles: tuple[str, ...] = (),
    extra_gate_net: str | None = None,
    extra_source_net: str | None = None,
) -> NetlistContract:
    """Build one supported MOSFET with controlled gate/source assignments."""
    numbers = dict(pin_numbers or {"drain": "1", "gate": "2", "source": "3"})
    if set(numbers) != {"drain", "gate", "source"}:
        raise ValueError("pin_numbers must map drain, gate, and source")

    functions = {
        f"Q1.{numbers['drain']}": "D",
        f"Q1.{numbers['gate']}": "G",
        f"Q1.{numbers['source']}": "S",
        "U1.1": "OUT",
    }
    functions.update(function_overrides or {})
    assignments: dict[str, list[str]] = {}
    role_nets = {
        "drain": "+5V",
        "gate": "SOURCE" if same_net else "GATE_CTRL",
        "source": "SOURCE",
    }
    for role, number in numbers.items():
        if role not in open_roles:
            assignments.setdefault(role_nets[role], []).append(f"Q1.{number}")
    assignments.setdefault(role_nets["gate"], []).append("U1.1")
    if extra_gate_net is not None:
        assignments.setdefault(extra_gate_net, []).append(f"Q1.{numbers['gate']}")
    if extra_source_net is not None:
        assignments.setdefault(extra_source_net, []).append(f"Q1.{numbers['source']}")

    return NetlistContract(
        components={
            "Q1": ComponentContract(value="Synthetic NMOS", footprint="Synthetic:TO-220"),
            "U1": ComponentContract(value="Synthetic gate driver", footprint="Synthetic:DIP-8"),
        },
        nets={net: tuple(pins) for net, pins in assignments.items()},
        dnp_components=dnp,
        component_symbols={"Q1": symbol, "U1": "Synthetic:Gate_Driver"},
        component_pin_numbers={"Q1": inventory, "U1": ("1",)},
        pin_functions=functions,
    )
