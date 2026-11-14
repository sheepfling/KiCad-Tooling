"""Conservative review hints for separately numbered schematic return nets."""

from __future__ import annotations

import re

from .netlist_contract_models import NetlistContract
from .return_net_models import ReturnNetGroup

_RETURN_WORDS = r"0V|GND[A-Z]?|AGND|DGND|PGND|VSS[A-Z]?|RTN|RETURN|GROUND|RET"
_INDEXED_NET = re.compile(r"^(?P<stem>.*?\D)[\s_./-]*(?P<index>\d+)$")
_INDEX_BEFORE_RETURN = re.compile(
    rf"^(?P<stem>.+?)(?P<separator>[\s_./-]*)(?P<index>\d+)"
    rf"[\s_./-]+(?P<return>{_RETURN_WORDS})$",
    re.IGNORECASE,
)
_RETURN_TOKEN = re.compile(rf"(?<![A-Z0-9])(?:{_RETURN_WORDS})(?![A-Z0-9])", re.IGNORECASE)
_VSS_SEGMENT = re.compile(r"(?<![A-Z0-9])VSS[A-Z0-9]*(?![A-Z0-9])", re.IGNORECASE)
_SERIAL_PROTOCOL_NUMBERS = frozenset({"rs232", "rs422", "rs485"})


def is_return_like_net_name(name: str) -> bool:
    """Recognize return-like net labels for review context, not pin-role inference."""
    return _RETURN_TOKEN.search(name) is not None


def is_vss_prefixed_net_name(name: str) -> bool:
    """Recognize VSS-prefixed label segments, which may denote a negative rail."""
    return _VSS_SEGMENT.search(name) is not None


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
    protocol_name = re.sub(
        r"[\s_./-]+", "", f"{stem}{match.group('separator')}{match.group('index')}"
    ).casefold()
    if (
        re.fullmatch(r"[A-Z][A-Z0-9]*", stem, re.IGNORECASE) is None
        or _RETURN_TOKEN.fullmatch(stem) is not None
        or protocol_name in _SERIAL_PROTOCOL_NUMBERS
    ):
        return None
    return f"{stem}_{match.group('return')}", int(match.group("index"))


def return_net_groups(observed: NetlistContract) -> tuple[ReturnNetGroup, ...]:
    """Find base-plus-indexed or numbered sibling returns for review only."""
    grouped: dict[str, list[tuple[str, int, str]]] = {}
    base_names: dict[str, list[str]] = {}
    for name in sorted(observed.nets):
        indexed = _indexed_return(name)
        if indexed is not None:
            stem, index = indexed
            key = re.sub(r"[\s_./-]+", "", stem).casefold()
            grouped.setdefault(key, []).append((name, index, stem))
            continue
        if _RETURN_TOKEN.search(name) is not None:
            key = re.sub(r"[\s_./-]+", "", name).casefold()
            base_names.setdefault(key, []).append(name)

    results: list[ReturnNetGroup] = []
    for key, entries in sorted(grouped.items()):
        bases = base_names.get(key, [])
        if len({index for _, index, _ in entries}) < 2 and not bases:
            continue
        names = sorted({name for name, _, _ in entries} | set(bases))
        results.append(
            ReturnNetGroup(
                stem=bases[0] if bases else entries[0][2],
                nets={name: observed.nets[name] for name in names},
            )
        )
    return tuple(results)


def return_label_groups_without_pin_roles(observed: NetlistContract) -> tuple[ReturnNetGroup, ...]:
    """Find multiple return-like labels whose mapped pins have no named return role."""
    numbered_net_names = {name for group in return_net_groups(observed) for name in group.nets}
    candidates = {
        name: tuple(sorted(pins))
        for name, pins in sorted(observed.nets.items())
        if pins
        and _RETURN_TOKEN.search(name) is not None
        and name not in numbered_net_names
        and not any(_RETURN_TOKEN.search(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    if len(candidates) < 2:
        return ()

    return (
        ReturnNetGroup(
            stem="return-like net labels without explicit pin roles",
            nets=candidates,
        ),
    )
