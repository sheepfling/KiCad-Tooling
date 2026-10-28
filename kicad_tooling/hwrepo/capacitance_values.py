"""Bounded parsing for explicit capacitor values in KiCad component fields."""

from __future__ import annotations

import re
from decimal import Decimal, DecimalException, InvalidOperation, localcontext
from types import MappingProxyType

_CAPACITANCE_VALUE = re.compile(
    r"^\s*(?P<number>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))\s*"
    r"(?P<unit>pf|nf|uf|μf|µf|p|n|u)\s*$",
    re.IGNORECASE,
)
_PICO_FARADS_PER_UNIT = MappingProxyType(
    {
        "p": Decimal(1),
        "pf": Decimal(1),
        "n": Decimal(1000),
        "nf": Decimal(1000),
        "u": Decimal(1000000),
        "uf": Decimal(1000000),
        "μf": Decimal(1000000),
        "µf": Decimal(1000000),
    }
)


def parse_capacitance_pf(value: str) -> Decimal | None:
    """Parse a deliberately small set of explicit KiCad capacitance spellings."""
    if len(value) > 128:
        return None
    match = _CAPACITANCE_VALUE.fullmatch(value)
    if match is None:
        return None
    try:
        number = Decimal(match.group("number"))
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    try:
        with localcontext() as context:
            context.prec = 50
            return number * _PICO_FARADS_PER_UNIT[match.group("unit").casefold()]
    except DecimalException:
        return None
