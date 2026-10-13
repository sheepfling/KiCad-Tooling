"""Typed observations for unreviewed numbered power-rail hints."""

from __future__ import annotations

from collections.abc import Mapping

from .model_primitives import NetName, NonEmptyText, Reference, StrictModel


class NumberedPowerRailGroup(StrictModel):
    """Unreviewed, similarly named numbered positive supply nets."""

    stem: NonEmptyText
    nets: Mapping[NetName, tuple[Reference, ...]]
