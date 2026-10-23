"""Synthetic MOSFET rail-order inputs shared by focused and hash-seed tests."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def mosfet_terminal_order_netlist(
    *,
    channel_type: str = "nmos",
    reversed_order: bool = True,
    symbol: str | None = None,
    pin_numbers: Mapping[str, str] | None = None,
    drain_net: str | None = None,
    source_net: str | None = None,
    inventory: tuple[str, ...] = ("1", "2", "3"),
    dnp: tuple[str, ...] = (),
    extra_drain_net: str | None = None,
    function_overrides: Mapping[str, str] | None = None,
) -> NetlistContract:
    """Build one supported MOSFET with a connected gate and varied D/S evidence."""
    if channel_type not in {"nmos", "pmos"}:
        raise ValueError("channel_type must be nmos or pmos")
    pins = dict(pin_numbers or {"drain": "1", "gate": "2", "source": "3"})
    if set(pins) != {"drain", "gate", "source"}:
        raise ValueError("pin_numbers must map drain, gate, and source")
    if symbol is None:
        symbol = f"Transistor_FET:Q_{channel_type.upper()}_GDS"

    if drain_net is None:
        drain_net = (
            ("GND" if channel_type == "nmos" else "+5V")
            if reversed_order
            else ("+5V" if channel_type == "nmos" else "GND")
        )
    if source_net is None:
        source_net = (
            ("+5V" if channel_type == "nmos" else "GND")
            if reversed_order
            else ("GND" if channel_type == "nmos" else "+5V")
        )

    numbers_by_role = {key: value for key, value in pins.items()}
    functions = {
        f"Q1.{numbers_by_role['drain']}": "D",
        f"Q1.{numbers_by_role['gate']}": "G",
        f"Q1.{numbers_by_role['source']}": "S",
        "U1.1": "OUT",
    }
    functions.update(function_overrides or {})
    drain_pin = f"Q1.{numbers_by_role['drain']}"
    source_pin = f"Q1.{numbers_by_role['source']}"
    gate_pin = f"Q1.{numbers_by_role['gate']}"
    nets: dict[str, tuple[str, ...]] = {
        drain_net: (drain_pin,),
        source_net: (source_pin,),
        "GATE_CTRL": (gate_pin, "U1.1"),
    }
    if extra_drain_net is not None:
        nets[extra_drain_net] = (drain_pin,)
    return NetlistContract(
        components={
            "Q1": ComponentContract(value="Synthetic MOSFET", footprint="Synthetic:TO-220"),
            "U1": ComponentContract(value="Synthetic gate driver", footprint="Synthetic:DIP-8"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "Q1": symbol,
            "U1": "Synthetic:Gate_Driver",
        },
        component_pin_numbers={"Q1": inventory, "U1": ("1",)},
        pin_functions=functions,
    )
