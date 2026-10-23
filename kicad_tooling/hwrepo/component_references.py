"""Bounded component-reference conventions shared by electrical analyses."""

from __future__ import annotations

import re

_INTEGRATED_CIRCUIT_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def is_integrated_circuit_reference(reference: str) -> bool:
    """Return whether a reference follows the bounded U/IC convention."""
    return _INTEGRATED_CIRCUIT_REFERENCE.fullmatch(reference) is not None
