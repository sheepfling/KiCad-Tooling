"""Exact built-in three-terminal MOSFET symbol identities used by component lints."""

from __future__ import annotations

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
