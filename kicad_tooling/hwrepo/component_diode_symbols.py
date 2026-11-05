"""Exact built-in diode identity and native anode/cathode role recognition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

SUPPORTED_TWO_TERMINAL_DIODE_SYMBOLS = frozenset({"device:d", "device:d_schottky"})


@dataclass(frozen=True, slots=True)
class DiodeTerminalNumbers:
    """Native pin numbers assigned to the diode anode and cathode roles."""

    anode: str
    cathode: str


def diode_terminal_numbers(
    reference: str,
    symbol: str,
    pin_numbers: Sequence[str],
    pin_functions: Mapping[str, str],
) -> DiodeTerminalNumbers | None:
    """Resolve exact supported two-pin diode identities with unique A/K roles."""
    numbers = tuple(pin_numbers)
    if (
        symbol.casefold() not in SUPPORTED_TWO_TERMINAL_DIODE_SYMBOLS
        or len(numbers) != 2
        or len({number.casefold() for number in numbers}) != 2
    ):
        return None

    functions = {
        pin.casefold(): function.strip().casefold() for pin, function in pin_functions.items()
    }
    anode: str | None = None
    cathode: str | None = None
    for number in numbers:
        role = functions.get(f"{reference}.{number}".casefold())
        if role == "a":
            if anode is not None:
                return None
            anode = number
        elif role == "k":
            if cathode is not None:
                return None
            cathode = number
    if anode is None or cathode is None:
        return None
    return DiodeTerminalNumbers(anode=anode, cathode=cathode)
