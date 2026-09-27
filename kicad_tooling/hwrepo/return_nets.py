"""Conservative review hints for separately numbered schematic return nets."""

from __future__ import annotations

import re

from .models import NetlistContract, ReturnNetGroup

_RETURN_WORDS = r"0V|GND|AGND|DGND|PGND|VSS|RTN|RETURN|GROUND"
_INDEXED_NET = re.compile(r"^(?P<stem>.*?\D)[\s_./-]*(?P<index>\d+)$")
_INDEX_BEFORE_RETURN = re.compile(
    rf"^(?P<stem>.+?)(?P<separator>[\s_./-]*)(?P<index>\d+)"
    rf"[\s_./-]+(?P<return>{_RETURN_WORDS})$",
    re.IGNORECASE,
)
_RETURN_TOKEN = re.compile(rf"(?<![A-Z0-9])(?:{_RETURN_WORDS})(?![A-Z0-9])", re.IGNORECASE)
_COMPACT_PORT_STEMS = frozenset({"USB", "UART", "SERIAL", "PORT", "COM"})


def _indexed_return(name: str) -> tuple[str, int] | None:
    match = _INDEXED_NET.fullmatch(name)
    if match is not None:
        stem = match.group("stem").rstrip(" _./-")
        if stem and _RETURN_TOKEN.search(stem) is not None:
            return stem, int(match.group("index"))
    match = _INDEX_BEFORE_RETURN.fullmatch(name)
    if match is None:
        return None
    stem = match.group("stem").rstrip(" _./-")
    if not match.group("separator") and stem.upper() not in _COMPACT_PORT_STEMS:
        return None
    return f"{stem}_{match.group('return')}", int(match.group("index"))


def return_net_groups(observed: NetlistContract) -> tuple[ReturnNetGroup, ...]:
    """Find numbered sibling returns for review, without inferring electrical intent."""
    grouped: dict[str, list[tuple[str, int, str]]] = {}
    for name in sorted(observed.nets):
        indexed = _indexed_return(name)
        if indexed is None:
            continue
        stem, index = indexed
        key = re.sub(r"[\s_./-]+", "", stem).casefold()
        grouped.setdefault(key, []).append((name, index, stem))
    return tuple(
        ReturnNetGroup(
            stem=entries[0][2],
            nets={name: observed.nets[name] for name, _, _ in entries},
        )
        for _, entries in sorted(grouped.items())
        if len({index for _, index, _ in entries}) > 1
    )
