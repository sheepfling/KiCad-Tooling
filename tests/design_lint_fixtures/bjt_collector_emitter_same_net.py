"""Synthetic basic-BJT terminal assignments for component lint."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def _bjt_terminal_pair_netlist(
    *,
    family: str = "npn",
    shared_roles: tuple[str, str] | None,
    shared_net: str,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    function_overrides: Mapping[str, str] | None = None,
    open_roles: tuple[str, ...] = (),
    extra_base_net: str | None = None,
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
    role_nets = {"base": "BASE_CTRL", "collector": "+5V", "emitter": "GND"}
    if shared_roles is not None:
        if len(shared_roles) != 2 or not set(shared_roles) <= set(role_nets):
            raise ValueError("shared_roles must name two distinct BJT terminal roles")
        if shared_roles[0] == shared_roles[1]:
            raise ValueError("shared_roles must name two distinct BJT terminal roles")
        role_nets[shared_roles[0]] = shared_net
        role_nets[shared_roles[1]] = shared_net
    assignments: dict[str, list[str]] = {}
    for role, number in numbers.items():
        if role not in open_roles:
            assignments.setdefault(role_nets[role], []).append(f"Q1.{number}")
    if extra_collector_net is not None:
        assignments.setdefault(extra_collector_net, []).append(f"Q1.{numbers['collector']}")
    if extra_base_net is not None:
        assignments.setdefault(extra_base_net, []).append(f"Q1.{numbers['base']}")

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
    """Build an NPN/PNP same-net fault or distinct-net control."""
    return _bjt_terminal_pair_netlist(
        family=family,
        shared_roles=("collector", "emitter") if same_net else None,
        shared_net="CE_SHARED",
        symbol=symbol,
        pin_numbers=pin_numbers,
        inventory=inventory,
        dnp=dnp,
        function_overrides=function_overrides,
        open_roles=open_roles,
        extra_collector_net=extra_collector_net,
    )


def bjt_base_emitter_netlist(
    *,
    family: str = "npn",
    same_net: bool = True,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    function_overrides: Mapping[str, str] | None = None,
    open_roles: tuple[str, ...] = (),
    extra_base_net: str | None = None,
) -> NetlistContract:
    """Build a native-role B/E same-net fault or distinct-net control."""
    return _bjt_terminal_pair_netlist(
        family=family,
        shared_roles=("base", "emitter") if same_net else None,
        shared_net="BE_SHARED",
        symbol=symbol,
        pin_numbers=pin_numbers,
        inventory=inventory,
        dnp=dnp,
        function_overrides=function_overrides,
        open_roles=open_roles,
        extra_base_net=extra_base_net,
    )
