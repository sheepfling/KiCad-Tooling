"""Exact built-in three-terminal MOSFET symbol identities used by component lints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS = frozenset(
    {
        "transistor_fet:q_nmos_dgs",
        "transistor_fet:q_nmos_dsg",
        "transistor_fet:q_nmos_gds",
        "transistor_fet:q_nmos_gsd",
        "transistor_fet:q_nmos_sgd",
        "transistor_fet:q_pmos_dgs",
        "transistor_fet:q_pmos_dsg",
        "transistor_fet:q_pmos_gds",
        "transistor_fet:q_pmos_gsd",
        "transistor_fet:q_pmos_sdg",
        "transistor_fet:q_pmos_sgd",
    }
)


def mosfet_channel_type(symbol: str) -> Literal["nmos", "pmos"] | None:
    """Return the channel family for an exact supported KiCad symbol identity."""
    normalized = symbol.strip().casefold()
    if normalized not in SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS:
        return None
    if normalized.startswith("transistor_fet:q_nmos_"):
        return "nmos"
    return "pmos"


_TERMINAL_FUNCTION_ROLES = {
    "d": "drain",
    "drain": "drain",
    "g": "gate",
    "gate": "gate",
    "s": "source",
    "source": "source",
}


def mosfet_terminal_role_numbers(
    reference: str,
    symbol: str,
    pin_numbers: Sequence[str],
    pin_functions: Mapping[str, str],
) -> dict[str, str] | None:
    """Map complete native D/G/S roles for an exact supported three-terminal MOSFET."""
    numbers = tuple(pin_numbers)
    if (
        mosfet_channel_type(symbol) is None
        or len(numbers) != 3
        or len({number.casefold() for number in numbers}) != 3
    ):
        return None

    functions = {pin.casefold(): value.strip().casefold() for pin, value in pin_functions.items()}
    roles: dict[str, str] = {}
    for number in numbers:
        role = _TERMINAL_FUNCTION_ROLES.get(functions.get(f"{reference}.{number}".casefold(), ""))
        if role is None:
            continue
        if role in roles:
            return None
        roles[role] = number
    return roles if set(roles) == {"drain", "gate", "source"} else None
