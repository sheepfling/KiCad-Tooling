"""Shared added, removed, and changed states for BOM comparisons."""

from __future__ import annotations

from .bom_compare_models import Change


def change_state(before: object | None, after: object | None) -> Change:
    return (
        "ADDED"
        if before is None
        else "REMOVED"
        if after is None
        else "UNCHANGED"
        if before == after
        else "CHANGED"
    )
