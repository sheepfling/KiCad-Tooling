"""Shared bounded syntax for numeric KiCad component-value fields."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_GROUPED_NUMBER = re.compile(r"^(?P<integer>[0-9]{1,3}(?: [0-9]{3})+)(?P<fraction>[.,][0-9]*)?$")
_DECIMAL_NUMBER = re.compile(r"^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")


def primary_component_value_text(value: str) -> tuple[str, bool] | None:
    """Return a bounded primary value and whether comma-delimited metadata follows."""
    if len(value) > 128:
        return None
    text = value.strip()
    if not text:
        return None
    separator = re.search(r",\s+", text)
    if separator is None:
        return text, False
    primary = text[: separator.start()].rstrip()
    if not primary:
        return None
    return primary, True


def parse_component_value_number(value: str) -> Decimal | None:
    """Parse an unsigned decimal token, rejecting ambiguous comma grouping."""
    if len(value) > 128:
        return None
    token = value.strip()
    grouped = _GROUPED_NUMBER.fullmatch(token)
    has_grouped_integer = grouped is not None
    if grouped is not None:
        fraction = grouped.group("fraction") or ""
        token = grouped.group("integer").replace(" ", "") + fraction
    elif any(character.isspace() for character in token):
        return None

    if "," in token:
        if token.count(",") != 1 or "." in token:
            return None
        whole, fractional = token.split(",")
        if (whole and not whole.isdigit()) or not fractional.isdigit():
            return None
        if whole and len(fractional) == 3 and not has_grouped_integer:
            return None
        token = f"{whole or '0'}.{fractional}"
    if _DECIMAL_NUMBER.fullmatch(token) is None:
        return None
    try:
        number = Decimal(token)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None
