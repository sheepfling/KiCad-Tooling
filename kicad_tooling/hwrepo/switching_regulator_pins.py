"""Exact native pin-function recognition shared by switching-regulator checks."""

from __future__ import annotations

import re

_SWITCH_NODE_FUNCTION = re.compile(r"(?:sw|lx|ph)\d*")


def is_switch_node_function(function: str) -> bool:
    """Recognize exact SW, LX, and PH pin-function names with optional digits."""
    return _SWITCH_NODE_FUNCTION.fullmatch(function.casefold()) is not None
