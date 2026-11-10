"""Bounded parsing for explicit capacitor values in KiCad component fields."""

from __future__ import annotations

import re
from decimal import Decimal, DecimalException, localcontext
from types import MappingProxyType

from .component_value_syntax import parse_component_value_number, primary_component_value_text

_CAPACITANCE_VALUE = re.compile(
    r"^\s*(?P<number>(?:[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]*)?|"
    r"[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+))\s*"
    r"(?P<unit>ff|pf|nf|uf|μf|µf|mf|f|p|n|u)\s*$",
    re.IGNORECASE,
)
_PICO_FARADS_PER_UNIT = MappingProxyType(
    {
        "ff": Decimal("0.001"),
        "p": Decimal(1),
        "pf": Decimal(1),
        "n": Decimal(1000),
        "nf": Decimal(1000),
        "u": Decimal(1000000),
        "mf": Decimal(1000000000),
        "f": Decimal(1000000000000),
        "uf": Decimal(1000000),
        "μf": Decimal(1000000),
        "µf": Decimal(1000000),
    }
)


def parse_capacitance_pf(value: str) -> Decimal | None:
    """Parse bounded KiCad capacitance spellings without guessing separators."""
    primary = primary_component_value_text(value)
    if primary is None:
        return None
    value_text, _has_metadata = primary
    match = _CAPACITANCE_VALUE.fullmatch(value_text)
    if match is None:
        return None
    number = parse_component_value_number(match.group("number"))
    if number is None or number <= 0:
        return None
    try:
        with localcontext() as context:
            context.prec = 50
            return number * _PICO_FARADS_PER_UNIT[match.group("unit").casefold()]
    except DecimalException:
        return None
