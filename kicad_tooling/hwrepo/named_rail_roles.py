"""Bounded role clues for schematic net labels that look like supply rails."""

from __future__ import annotations

from typing import Literal, TypeAlias

from .connector_identity import is_named_supply_function
from .return_nets import is_return_like_net_name

NamedRailRoleClue: TypeAlias = Literal["supply-like", "return-like"]


def named_rail_role_clue(net_name: str) -> NamedRailRoleClue | None:
    """Classify a narrow supply/return label without claiming electrical potential."""
    if is_named_supply_function(net_name):
        return "supply-like"
    if is_return_like_net_name(net_name):
        return "return-like"
    return None
