"""Bounded exact-condition reasoning shared by PCB custom-rule coverage checks."""

from __future__ import annotations

import re

_EXACT_NET_CONDITION = re.compile(r"A\.NetName == '([^'\\*?\r\n]+)'")
_EXACT_NETCLASS_CONDITION = re.compile(r"A\.NetClass == '([^'\\*?,$\x00-\x1f\x7f]+)'")
_EXACT_REFERENCE_CONDITION = re.compile(r"A\.Reference == '([^'\\*?$\x00-\x1f\x7f]+)'")
_EXACT_FROM_TO_CONDITION = re.compile(
    r"A\.fromTo\('([A-Za-z0-9_-]+-[A-Za-z0-9_-]+)', "
    r"'([A-Za-z0-9_-]+-[A-Za-z0-9_-]+)'\)"
)
_EXACT_DIFF_PAIR_CONDITION = re.compile(r"A\.inDiffPair\('([^'\\*?$\x00-\x1f\x7f]+)'\)")


def native_exact_net_condition(condition: str) -> str | None:
    """Return the literal net from a supported exact KiCad net selector."""
    match = _EXACT_NET_CONDITION.fullmatch(condition)
    return None if match is None else match.group(1)


def native_exact_netclass_condition(condition: str) -> str | None:
    """Return one supported literal class selector, excluding composite lists."""
    match = _EXACT_NETCLASS_CONDITION.fullmatch(condition)
    return None if match is None else match.group(1)


def native_exact_reference_condition(condition: str) -> str | None:
    """Return one supported exact component-reference selector."""
    match = _EXACT_REFERENCE_CONDITION.fullmatch(condition)
    return None if match is None else match.group(1)


def native_exact_from_to_condition(condition: str) -> tuple[str, str] | None:
    """Return two literal pad selectors from a supported exact fromTo selector."""
    match = _EXACT_FROM_TO_CONDITION.fullmatch(condition)
    return None if match is None else (match.group(1), match.group(2))


def native_exact_diff_pair_condition(condition: str) -> str | None:
    """Return a supported literal KiCad differential-pair selector."""
    match = _EXACT_DIFF_PAIR_CONDITION.fullmatch(condition)
    return None if match is None else match.group(1)


def native_net_conditions_are_disjoint(first: str, second: str) -> bool:
    """Prove disjointness only for two exact, literal KiCad A.NetName selectors."""
    first_net = native_exact_net_condition(first)
    second_net = native_exact_net_condition(second)
    return bool(first_net and second_net and first_net.casefold() != second_net.casefold())
