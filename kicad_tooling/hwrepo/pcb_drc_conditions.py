"""Bounded exact-condition reasoning shared by PCB custom-rule coverage checks."""

from __future__ import annotations

import re

_EXACT_NET_CONDITION = re.compile(r"A\.NetName == '([^'\\*?\r\n]+)'")


def native_net_conditions_are_disjoint(first: str, second: str) -> bool:
    """Prove disjointness only for two exact, literal KiCad A.NetName selectors."""
    first_net = _EXACT_NET_CONDITION.fullmatch(first)
    second_net = _EXACT_NET_CONDITION.fullmatch(second)
    return bool(
        first_net and second_net and first_net.group(1).casefold() != second_net.group(1).casefold()
    )
