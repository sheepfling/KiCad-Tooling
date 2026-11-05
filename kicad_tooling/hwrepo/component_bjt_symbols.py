"""Bounded symbol and terminal-role recognition for basic BJT lint rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

BjtTerminalRole: TypeAlias = Literal["base", "collector", "emitter"]


@dataclass(frozen=True, slots=True)
class BjtPinRoleNumbers:
    """Native pin numbers for the complete roles of one supported BJT."""

    base: str
    collector: str
    emitter: str


SUPPORTED_BASIC_BJT_SYMBOLS = frozenset(
    f"transistor_bjt:q_{family}_{order}"
    for family in ("npn", "pnp")
    for order in ("bce", "bec", "cbe", "ceb", "ebc", "ecb")
)

_FUNCTION_ROLES: Mapping[str, BjtTerminalRole] = MappingProxyType(
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
) -> BjtPinRoleNumbers | None:
    """Map complete native B/C/E roles for an exact supported basic BJT symbol."""
    numbers = tuple(pin_numbers)
    if (
        symbol.casefold() not in SUPPORTED_BASIC_BJT_SYMBOLS
        or len(numbers) != 3
        or len({number.casefold() for number in numbers}) != 3
    ):
        return None

    functions = {pin.casefold(): value.strip().casefold() for pin, value in pin_functions.items()}
    roles: dict[BjtTerminalRole, str] = {}
    for number in numbers:
        role = _FUNCTION_ROLES.get(functions.get(f"{reference}.{number}".casefold(), ""))
        if role is None:
            continue
        if role in roles:
            return None
        roles[role] = number
    if set(roles) != {"base", "collector", "emitter"}:
        return None
    return BjtPinRoleNumbers(
        base=roles["base"],
        collector=roles["collector"],
        emitter=roles["emitter"],
    )
