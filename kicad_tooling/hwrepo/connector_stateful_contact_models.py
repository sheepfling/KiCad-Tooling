"""Project-authored maps for connector contacts that change state mechanically."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NonEmptyText, StrictModel


class ConnectorStatefulContactPair(StrictModel):
    """Two physical contacts whose connection changes with an external state."""

    id: Identifier
    first_pin: NonEmptyText
    second_pin: NonEmptyText
    closed_when: Literal["plug_inserted", "plug_removed"]
    source_basis: NonEmptyText

    @model_validator(mode="after")
    def distinct_contact_pins(self) -> ConnectorStatefulContactPair:
        if self.first_pin.casefold() == self.second_pin.casefold():
            raise ValueError("A stateful contact pair must name two distinct pins")
        return self


class ConnectorStatefulContactRequirement(StrictModel):
    """Exact source identity and switch-contact map for one connector."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_value: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    native_pin_numbers: Annotated[tuple[NonEmptyText, ...], Field(min_length=2)]
    contact_pairs: Annotated[tuple[ConnectorStatefulContactPair, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_exact_contact_inventory(self) -> ConnectorStatefulContactRequirement:
        numbers = tuple(pin.casefold() for pin in self.native_pin_numbers)
        if len(set(numbers)) != len(numbers):
            raise ValueError("Stateful connector native pin numbers must be unique")
        pair_ids = tuple(pair.id.casefold() for pair in self.contact_pairs)
        if len(set(pair_ids)) != len(pair_ids):
            raise ValueError("Stateful connector contact-pair IDs must be unique")
        pair_pins = tuple(
            pin.casefold()
            for pair in self.contact_pairs
            for pin in (pair.first_pin, pair.second_pin)
        )
        if len(set(pair_pins)) != len(pair_pins):
            raise ValueError("A connector pin may appear in only one mapped stateful contact pair")
        if not set(pair_pins) <= set(numbers):
            raise ValueError("Mapped stateful contact pins must be in the exact native inventory")
        return self


class ConnectorStatefulContactMap(StrictModel):
    """Reviewed connector contact states used by deterministic schematic lint."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[ConnectorStatefulContactRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_stateful_connectors(self) -> ConnectorStatefulContactMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Stateful connector requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("A connector reference may have only one stateful contact map")
        return self
