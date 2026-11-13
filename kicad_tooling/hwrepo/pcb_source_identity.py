"""Canonical KiCad PCB UUID text shared by source-integrity checks."""

from __future__ import annotations

from uuid import UUID


def canonical_pcb_uuid(value: str) -> str | None:
    """Return canonical hyphenated UUID text, normalizing hexadecimal case."""
    try:
        parsed = str(UUID(value))
    except (AttributeError, ValueError):
        return None
    return parsed if parsed == value.lower() else None
