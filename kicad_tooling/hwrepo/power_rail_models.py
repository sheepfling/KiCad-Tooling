"""Typed observations for unreviewed numbered power-rail hints."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import field_validator

from .model_primitives import NetName, NonEmptyText, Reference, StrictModel


class NumberedPowerRailGroup(StrictModel):
    """Unreviewed, similarly named numbered positive supply nets."""

    stem: NonEmptyText
    nets: Mapping[NetName, tuple[Reference, ...]]

    @field_validator("nets")
    @classmethod
    def freeze_nets(
        cls,
        nets: Mapping[NetName, tuple[Reference, ...]],
    ) -> Mapping[NetName, tuple[Reference, ...]]:
        """Keep the nested map immutable with the frozen source record."""
        return MappingProxyType({name: tuple(references) for name, references in nets.items()})
