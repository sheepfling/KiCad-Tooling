"""Synthetic basic-BJT collector/emitter connectivity for component lint."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def bjt_collector_emitter_netlist(
    *,
    family: str = "npn",
    same_net: bool = True,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    function_overrides: Mapping[str, str] | None = None,
    open_roles: tuple[str, ...] = (),
    extra_collector_net: str | None = None,
) -> NetlistContract:
    """Build one supported BJT with controllable native pin and net evidence."""
    if family not in {"npn", "pnp"}:
        raise ValueError("family must be npn or pnp")
    numbers = dict(pin_numbers or {"base": "1", "collector": "2", "emitter": "3"})
    if set(numbers) != {"base", "collector", "emitter"}:
        raise ValueError("pin_numbers must map base, collector, and emitter")
    if symbol is None:
        symbol = f"Transistor_BJT:Q_{family.upper()}_BCE"

    functions = {
        f"Q1.{numbers['base']}": "B",
        f"Q1.{numbers['collector']}": "C",
        f"Q1.{numbers['emitter']}": "E",
    }
    functions.update(function_overrides or {})
    role_nets = {
        "base": "BASE_CTRL",
        "collector": "CE_SHARED" if same_net else "+5V",
        "emitter": "CE_SHARED" if same_net else "GND",
    }
    assignments: dict[str, list[str]] = {}
    for role, number in numbers.items():
        if role not in open_roles:
            assignments.setdefault(role_nets[role], []).append(f"Q1.{number}")
    if extra_collector_net is not None:
        assignments.setdefault(extra_collector_net, []).append(f"Q1.{numbers['collector']}")

    return NetlistContract(
        components={
            "Q1": ComponentContract(
                value=f"Synthetic {family.upper()}", footprint="Synthetic:TO-92"
            )
        },
        nets={net: tuple(pins) for net, pins in assignments.items()},
        dnp_components=dnp,
        component_symbols={"Q1": symbol},
        component_pin_numbers={"Q1": inventory},
        pin_functions=functions,
    )
