"""Typed project-authored connector contact current rating contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    StrictModel,
)


class ConnectorContactCurrentRequirement(StrictModel):
    """One exact connector contact's sourced rating and authored current load."""

    id: Identifier
    pin_number: NonEmptyText
    expected_function: NonEmptyText
    expected_net: NetName
    rated_current_a: ElectricalPositive
    derated_allowable_current_a: ElectricalPositive
    maximum_expected_current_a: NonNegativeMeasure
    maximum_utilization_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    rating_source: NonEmptyText
    rating_conditions: NonEmptyText
    derating_basis: NonEmptyText
    load_basis: NonEmptyText

    @model_validator(mode="after")
    def allowable_contact_current_within_rating(self) -> ConnectorContactCurrentRequirement:
        if self.derated_allowable_current_a > self.rated_current_a:
            raise ValueError(
                "Derated allowable current cannot exceed the source-rated contact current"
            )
        return self


class ConnectorContactRatingRequirement(StrictModel):
    """Exact native connector identity and one or more authored contact limits."""

    id: Identifier
    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    expected_part_id: Identifier
    native_pin_numbers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    contacts: Annotated[tuple[ConnectorContactCurrentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_connector_pin_inventory(self) -> ConnectorContactRatingRequirement:
        if len({pin.casefold() for pin in self.native_pin_numbers}) != len(self.native_pin_numbers):
            raise ValueError("Connector contact rating pin inventory must be unique")
        if len({contact.id.casefold() for contact in self.contacts}) != len(self.contacts):
            raise ValueError("Connector contact rating IDs must be unique per connector")
        contact_pins = [contact.pin_number.casefold() for contact in self.contacts]
        if len(set(contact_pins)) != len(contact_pins):
            raise ValueError("A connector pin may have only one contact current requirement")
        inventory = {pin.casefold() for pin in self.native_pin_numbers}
        if any(pin not in inventory for pin in contact_pins):
            raise ValueError("Rated connector contacts must be in the exact native pin inventory")
        return self


class ConnectorContactRatingAnalysis(StrictModel):
    """Project-owned comparison of per-contact current to reviewed connector ratings."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    requirements: Annotated[tuple[ConnectorContactRatingRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_connectors(self) -> ConnectorContactRatingAnalysis:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Connector contact rating requirement IDs must be unique")
        if len({item.reference.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Each connector may have one contact rating requirement")
        return self
