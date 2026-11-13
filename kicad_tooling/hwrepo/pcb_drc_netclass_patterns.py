"""Deterministic analysis of KiCad PCB netclass pattern assignments."""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass

from .json_object_pairs import (
    JsonObjectPairs,
    retain_json_object_pairs,
    unique_json_array_member,
    unique_json_object_member,
    unique_json_string_member,
)
from .pcb_board_net_inventory import pcb_board_net_names


@dataclass(frozen=True, slots=True)
class PcbUnmatchedNetClassPattern:
    """One valid non-default netclass pattern that matches no current board net."""

    pattern_index: int
    pattern: str
    netclass: str


def unmatched_pcb_netclass_patterns(
    project_settings_document: str,
    board_document: str,
) -> tuple[PcbUnmatchedNetClassPattern, ...]:
    """Find supported explicit class patterns that currently match no PCB net.

    KiCad patterns accept filename-style wildcards and regular expressions.
    Malformed or ambiguous project/board inventories are outside this review.
    """
    board_nets = pcb_board_net_names(board_document)
    if board_nets is None:
        return ()
    configured = _configured_netclass_patterns(project_settings_document)
    if configured is None:
        return ()
    class_names, patterns = configured
    return tuple(
        PcbUnmatchedNetClassPattern(index, pattern, netclass)
        for index, pattern, netclass in patterns
        if netclass != "Default"
        and netclass in class_names
        and not any(_kicad_netclass_pattern_matches(pattern, net) for net in board_nets)
    )


def _configured_netclass_patterns(
    document: str,
) -> tuple[frozenset[str], tuple[tuple[int, str, str], ...]] | None:
    """Read only unique, well-shaped class and pattern inventories."""
    try:
        root = json.loads(document, object_pairs_hook=retain_json_object_pairs)
    except (json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(root, JsonObjectPairs):
        return None
    net_settings = unique_json_object_member(root, "net_settings")
    if not isinstance(net_settings, JsonObjectPairs):
        return None
    classes = unique_json_array_member(net_settings, "classes")
    pattern_entries = unique_json_array_member(net_settings, "netclass_patterns")
    if classes is None or pattern_entries is None:
        return None

    class_names: list[str] = []
    for entry in classes:
        if not isinstance(entry, JsonObjectPairs):
            return None
        name = unique_json_string_member(entry, "name")
        if name is None or not name or name in class_names:
            return None
        class_names.append(name)
    if "Default" not in class_names:
        return None

    patterns: list[tuple[int, str, str]] = []
    for index, entry in enumerate(pattern_entries):
        if not isinstance(entry, JsonObjectPairs):
            continue
        pattern = unique_json_string_member(entry, "pattern")
        netclass = unique_json_string_member(entry, "netclass")
        if pattern and netclass:
            patterns.append((index, pattern, netclass))
    return frozenset(class_names), tuple(patterns)


def _kicad_netclass_pattern_matches(pattern: str, net: str) -> bool:
    """Match the measured KiCad combined wildcard/regular-expression syntax."""
    if fnmatch.fnmatchcase(net, pattern):
        return True
    try:
        return re.fullmatch(pattern, net) is not None
    except re.error:
        return False
