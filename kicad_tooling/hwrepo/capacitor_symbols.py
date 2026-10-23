"""Bounded recognition of native capacitor symbol identities."""

from __future__ import annotations


def is_capacitor_symbol(symbol: str) -> bool:
    """Return whether a library symbol ID has a recognized capacitor name.

    Common ``C``/``CP`` symbol families and explicitly capacitor-named symbol
    parts are candidates. This is identity-based screening, not proof that a
    custom part is a capacitor or that its value and behavior are valid.
    """
    library, separator, part = symbol.partition(":")
    if separator and (not library or not part or ":" in part):
        return False
    name = (part if separator else symbol).casefold()
    return name in {"c", "cp"} or name.startswith(("c_", "cp_")) or "capacitor" in name
