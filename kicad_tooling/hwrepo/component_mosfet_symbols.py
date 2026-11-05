"""Exact built-in three-terminal MOSFET symbol identities used by component lints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

MosfetTerminalRole: TypeAlias = Literal["drain", "gate", "source"]


@dataclass(frozen=True, slots=True)
class MosfetPinRoleNumbers:
    """Native pin numbers for the complete roles of one supported MOSFET."""

    drain: str
    gate: str
    source: str


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


_TERMINAL_FUNCTION_ROLES: Mapping[str, MosfetTerminalRole] = MappingProxyType(
    {
        "d": "drain",
        "drain": "drain",
        "g": "gate",
        "gate": "gate",
        "s": "source",
        "source": "source",
    }
)


def mosfet_terminal_role(function: str | None) -> MosfetTerminalRole | None:
    """Return a recognized native D/G/S role from one pin function."""
    if function is None:
        return None
    return _TERMINAL_FUNCTION_ROLES.get(function.strip().casefold())


def mosfet_terminal_role_numbers(
    reference: str,
    symbol: str,
    pin_numbers: Sequence[str],
    pin_functions: Mapping[str, str],
) -> MosfetPinRoleNumbers | None:
    """Map complete native D/G/S roles for an exact supported three-terminal MOSFET."""
    numbers = tuple(pin_numbers)
    if (
        mosfet_channel_type(symbol) is None
        or len(numbers) != 3
        or len({number.casefold() for number in numbers}) != 3
    ):
        return None

    functions = {pin.casefold(): value for pin, value in pin_functions.items()}
    roles: dict[MosfetTerminalRole, str] = {}
    for number in numbers:
        role = mosfet_terminal_role(functions.get(f"{reference}.{number}".casefold()))
        if role is None:
            continue
        if role in roles:
            return None
        roles[role] = number
    if set(roles) != {"drain", "gate", "source"}:
        return None
    return MosfetPinRoleNumbers(
        drain=roles["drain"],
        gate=roles["gate"],
        source=roles["source"],
    )
