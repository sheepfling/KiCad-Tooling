"""Exact built-in polarized-capacitor symbols and terminal-number roles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

SUPPORTED_POLARIZED_CAPACITOR_SYMBOLS = frozenset(
    {
        "device:c_polarized",
        "device:c_polarized_small",
        "device:c_polarized_us",
        "device:c_polarized_small_us",
    }
)


@dataclass(frozen=True, slots=True)
class PolarizedCapacitorTerminalNumbers:
    """Native pin numbers for the positive and negative capacitor terminals."""

    positive: Literal["1"] = "1"
    negative: Literal["2"] = "2"


def polarized_capacitor_terminal_numbers(
    symbol: str,
    pin_numbers: Sequence[str],
) -> PolarizedCapacitorTerminalNumbers | None:
    """Resolve the exact supported two-pin inventory with native 1+/2- roles."""
    numbers = tuple(number.casefold() for number in pin_numbers)
    if (
        symbol.casefold() not in SUPPORTED_POLARIZED_CAPACITOR_SYMBOLS
        or len(numbers) != 2
        or frozenset(numbers) != frozenset(("1", "2"))
    ):
        return None
    return PolarizedCapacitorTerminalNumbers()
