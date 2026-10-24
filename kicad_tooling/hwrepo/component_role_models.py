"""Project-owned identities for reviewed custom two-pin component roles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NonEmptyText, StrictModel


class ComponentRolePin(StrictModel):
    """One exact native pin signature used to classify a custom component."""

    number: NonEmptyText
    function: NonEmptyText
    electrical_type: NonEmptyText


class ComponentRoleBinding(StrictModel):
    """Project-reviewed role for one exact part, symbol, footprint and pin set."""

    part_id: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    role: Literal["led", "capacitor", "battery"]
    pins: Annotated[tuple[ComponentRolePin, ...], Field(min_length=2)]
    basis: NonEmptyText

    @model_validator(mode="after")
    def complete_unique_pin_signature(self) -> ComponentRoleBinding:
        numbers = tuple(item.number for item in self.pins)
        if len(numbers) != 2 or len(set(numbers)) != len(numbers):
            raise ValueError("Component role maps require exactly two unique native pins")
        if self.role in {"capacitor", "battery"} and any(
            item.electrical_type.casefold() != "passive" for item in self.pins
        ):
            raise ValueError(f"The {self.role} role requires two native passive pins")
        return self


class ComponentRoleMap(StrictModel):
    """Opt-in project classification for exact custom component identities."""

    entries: Annotated[tuple[ComponentRoleBinding, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_part_identities(self) -> ComponentRoleMap:
        identifiers = tuple(item.part_id.casefold() for item in self.entries)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Component role-map PART_ID entries must be unique")
        return self
