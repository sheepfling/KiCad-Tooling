"""Synthetic fitted SWD endpoints with controlled named-rail assignments."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

DEFAULT_FUNCTIONS = (
    "SYS_JTMS-SWDIO",
    "SYS_JTCK-SWCLK",
    "GPIO_AUX",
    "GPIO_OTHER",
)


def swd_signal_named_rail_netlist(
    *,
    reference: str = "U1",
    functions: tuple[str, ...] = DEFAULT_FUNCTIONS,
    rail_pins: Mapping[str, str] | None = None,
    dnp: bool = False,
    inventory: tuple[str, ...] | None = None,
    extra_assignments: Mapping[str, tuple[str, ...]] | None = None,
    omit_function_pins: frozenset[str] = frozenset(),
) -> NetlistContract:
    """Build a complete synthetic SWD target or explicitly named connector."""
    is_connector = reference.casefold().startswith("j")
    pin_numbers = tuple(str(index) for index in range(1, len(functions) + 1))
    function_map = {
        f"{reference}.{number}": function
        for number, function in zip(pin_numbers, functions, strict=True)
        if number not in omit_function_pins
    }
    assignments = {
        (rail_pins or {}).get(number, f"SWD_SIGNAL_{number}"): (f"{reference}.{number}",)
        for number in pin_numbers
    }
    assignments.update(extra_assignments or {})
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic SWD connector" if is_connector else "Synthetic SWD target",
                footprint="Synthetic:Conn_01x04" if is_connector else "Synthetic:QFN",
            )
        },
        nets=assignments,
        component_symbols={
            reference: (
                "Connector_Generic:Conn_01x04" if is_connector else "Synthetic:SwdDebugTarget"
            )
        },
        component_pin_numbers={reference: inventory or pin_numbers},
        pin_functions=function_map,
        pin_electrical_types={pin: "passive" for pin in function_map},
        dnp_components=(reference,) if dnp else (),
    )
