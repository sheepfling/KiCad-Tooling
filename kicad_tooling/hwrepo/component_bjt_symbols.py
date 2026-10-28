"""Bounded symbol and terminal-role recognition for basic BJT lint rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

SUPPORTED_BASIC_BJT_SYMBOLS = frozenset(
    f"transistor_bjt:q_{family}_{order}"
    for family in ("npn", "pnp")
    for order in ("bce", "bec", "cbe", "ceb", "ebc", "ecb")
)

_FUNCTION_ROLES = MappingProxyType(
    {
        "b": "base",
        "base": "base",
        "c": "collector",
        "collector": "collector",
        "e": "emitter",
        "emitter": "emitter",
    }
)


def basic_bjt_role_numbers(
    reference: str,
    symbol: str,
    pin_numbers: Sequence[str],
    pin_functions: Mapping[str, str],
) -> dict[str, str] | None:
    """Map complete native B/C/E roles for an exact supported basic BJT symbol."""
    numbers = tuple(pin_numbers)
    if (
        symbol.casefold() not in SUPPORTED_BASIC_BJT_SYMBOLS
        or len(numbers) != 3
        or len({number.casefold() for number in numbers}) != 3
    ):
        return None

    functions = {pin.casefold(): value.strip().casefold() for pin, value in pin_functions.items()}
    roles: dict[str, str] = {}
    for number in numbers:
        role = _FUNCTION_ROLES.get(functions.get(f"{reference}.{number}".casefold(), ""))
        if role is None:
            continue
        if role in roles:
            return None
        roles[role] = number
    return roles if set(roles) == {"base", "collector", "emitter"} else None
