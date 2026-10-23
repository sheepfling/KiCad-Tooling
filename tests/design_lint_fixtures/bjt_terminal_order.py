"""Synthetic NPN/PNP rail-order inputs for focused and hash-seed tests."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def bjt_terminal_order_netlist(
    *,
    family: str = "npn",
    reversed_order: bool = True,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    collector_net: str | None = None,
    emitter_net: str | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    extra_collector_net: str | None = None,
    function_overrides: Mapping[str, str] | None = None,
) -> NetlistContract:
    """Build one supported synthetic BJT with varied rail and pin evidence."""
    if family not in {"npn", "pnp"}:
        raise ValueError("family must be npn or pnp")
    pins = dict(pin_numbers or {"base": "1", "collector": "2", "emitter": "3"})
    if set(pins) != {"base", "collector", "emitter"}:
        raise ValueError("pin_numbers must map base, collector, and emitter")
    if symbol is None:
        symbol = f"Transistor_BJT:Q_{family.upper()}_BCE"

    if collector_net is None:
        collector_net = (
            ("GND" if family == "npn" else "+5V")
            if reversed_order
            else ("+5V" if family == "npn" else "GND")
        )
    if emitter_net is None:
        emitter_net = (
            ("+5V" if family == "npn" else "GND")
            if reversed_order
            else ("GND" if family == "npn" else "+5V")
        )

    numbers = {role: number for role, number in pins.items()}
    functions = {
        f"Q1.{numbers['base']}": "B",
        f"Q1.{numbers['collector']}": "C",
        f"Q1.{numbers['emitter']}": "E",
    }
    functions.update(function_overrides or {})
    collector_pin = f"Q1.{numbers['collector']}"
    emitter_pin = f"Q1.{numbers['emitter']}"
    base_pin = f"Q1.{numbers['base']}"
    nets: dict[str, tuple[str, ...]] = {
        collector_net: (collector_pin,),
        emitter_net: (emitter_pin,),
        "BASE_CTRL": (base_pin,),
    }
    if extra_collector_net is not None:
        nets[extra_collector_net] = (collector_pin,)

    return NetlistContract(
        components={"Q1": ComponentContract(value="Synthetic BJT", footprint="Synthetic:TO-92")},
        nets=nets,
        dnp_components=dnp,
        component_symbols={"Q1": symbol},
        component_pin_numbers={"Q1": inventory},
        pin_functions=functions,
    )
