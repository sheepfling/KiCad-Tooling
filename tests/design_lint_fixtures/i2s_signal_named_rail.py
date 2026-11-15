"""Synthetic I2S endpoint pins assigned to neutral labels or named rails."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

DEFAULT_FUNCTIONS = ("I2S_BCLK", "I2S_LRCLK", "I2S_DATA", "I2S_MCLK")


def i2s_signal_named_rail_netlist(
    *,
    reference: str = "U1",
    functions: tuple[str, ...] = DEFAULT_FUNCTIONS,
    rail_pins: Mapping[str, str] | None = None,
    dnp: bool = False,
    inventory: tuple[str, ...] | None = None,
    extra_assignments: Mapping[str, tuple[str, ...]] | None = None,
    omit_function_pins: frozenset[str] = frozenset(),
) -> NetlistContract:
    """Build a complete synthetic I2S IC or connector with controlled assignments."""
    is_connector = reference.casefold().startswith("j")
    pin_numbers = tuple(str(index) for index in range(1, len(functions) + 1))
    function_map = {
        f"{reference}.{number}": function
        for number, function in zip(pin_numbers, functions, strict=True)
        if number not in omit_function_pins
    }
    assignments = {
        (rail_pins or {}).get(number, f"AUDIO_SIGNAL_{number}"): (f"{reference}.{number}",)
        for number in pin_numbers
    }
    assignments.update(extra_assignments or {})
    symbol = "Connector_Generic:Conn_01x04" if is_connector else "Synthetic:I2SAudioCodec"
    value = "Synthetic I2S connector" if is_connector else "Synthetic I2S codec"
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=value,
                footprint="Synthetic:QFN" if not is_connector else "Synthetic:Conn_01x04",
            )
        },
        nets=assignments,
        component_symbols={reference: symbol},
        component_pin_numbers={reference: inventory or pin_numbers},
        pin_functions=function_map,
        pin_electrical_types={pin: "passive" for pin in function_map},
        dnp_components=(reference,) if dnp else (),
    )
