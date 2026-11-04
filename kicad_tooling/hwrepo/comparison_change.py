"""Compare two optional values using the shared before/after state contract."""

from __future__ import annotations

from typing import TypeVar

from .comparison_change_models import Change

_ComparedValue = TypeVar("_ComparedValue")


def change_state(before: _ComparedValue | None, after: _ComparedValue | None) -> Change:
    """Return the change state for one pair of values of the same type."""
    return (
        "ADDED"
        if before is None
        else "REMOVED"
        if after is None
        else "UNCHANGED"
        if before == after
        else "CHANGED"
    )
