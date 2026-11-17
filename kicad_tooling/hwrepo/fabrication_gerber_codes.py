"""Parsing primitives for bounded Gerber aperture identifiers."""

from __future__ import annotations

import re

_APERTURE_NUMBER_MAX = 0x7FFFFFFF


def parse_gerber_aperture_number(raw: str) -> int | None:
    """Return a standard ASCII Gerber D-code number, or ``None`` if invalid."""
    if re.fullmatch(r"[0-9]+", raw) is None:
        return None
    normalized = raw.lstrip("0") or "0"
    if len(normalized) > 10:
        return None
    number = int(normalized)
    if not 10 <= number <= _APERTURE_NUMBER_MAX:
        return None
    return number
