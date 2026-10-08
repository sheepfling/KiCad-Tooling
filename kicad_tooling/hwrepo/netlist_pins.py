"""Helpers for interpreting KiCad's exported pin-assignment records."""

from __future__ import annotations


def is_native_unconnected_net_name(name: str) -> bool:
    """Recognize KiCad's generated per-pin nets for pins without assignments."""
    normalized = name.casefold()
    return normalized.startswith("unconnected-(") and normalized.endswith(")")
