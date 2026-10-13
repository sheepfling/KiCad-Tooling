"""Typed observations for unreviewed return-net grouping hints."""

from __future__ import annotations

from collections.abc import Mapping

from .model_primitives import NetName, NonEmptyText, Reference, StrictModel


class ReturnNetGroup(StrictModel):
    """Unreviewed, similarly named return nets observed in a native export."""

    stem: NonEmptyText
    nets: Mapping[NetName, tuple[Reference, ...]]
