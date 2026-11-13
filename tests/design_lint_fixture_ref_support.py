"""Shared naming helper for design-lint parity fixture references."""

from __future__ import annotations


def _refs(owner: str, *tests: str) -> tuple[str, ...]:
    return tuple(f"{owner}.{name}" for name in tests)
